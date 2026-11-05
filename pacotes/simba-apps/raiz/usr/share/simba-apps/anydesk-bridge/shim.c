/*
 * anydesk-bridge shim — carregado via LD_PRELOAD apenas no serviço do AnyDesk.
 *
 * O AnyDesk recusa sessões cujo logind informa Type=wayland. Quando a ponte
 * (Xvfb espelhando o Hyprland via wayvnc) está ativa para o dono da sessão,
 * este shim faz o AnyDesk enxergar a sessão como Type=x11 com Display=<ponte>.
 * O estado da ponte é lido de /run/user/<uid>/anydesk-bridge/display.
 * Nada muda para o restante do sistema.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <gio/gio.h>
#include <pwd.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define LOGIND_SESSION "org.freedesktop.login1.Session"
#define LOG_PATH "/var/log/anydesk-bridge-shim.log"

static void logf_(const char *fmt, ...) {
    if (getuid() != 0) return;
    FILE *f = fopen(LOG_PATH, "a");
    if (!f) return;
    time_t t = time(NULL);
    char ts[32];
    strftime(ts, sizeof ts, "%F %T", localtime(&t));
    fprintf(f, "%s [%d] ", ts, getpid());
    va_list ap;
    va_start(ap, fmt);
    vfprintf(f, fmt, ap);
    va_end(ap);
    fputc('\n', f);
    fclose(f);
}

/* Retorna o display da ponte (ex.: ":5") se ela estiver ativa para o uid. */
static gboolean bridge_display(guint32 uid, char *out, size_t len) {
    char path[128];
    snprintf(path, sizeof path, "/run/user/%u/anydesk-bridge/display", uid);
    struct stat st;
    if (stat(path, &st) != 0 || st.st_uid != uid) return FALSE;
    FILE *f = fopen(path, "r");
    if (!f) return FALSE;
    gboolean ok = fgets(out, (int)len, f) != NULL;
    fclose(f);
    if (!ok) return FALSE;
    out[strcspn(out, "\r\n")] = 0;
    if (out[0] != ':') return FALSE;
    /* Confere se o socket do X da ponte existe de fato. */
    char sock[64];
    snprintf(sock, sizeof sock, "/tmp/.X11-unix/X%s", out + 1);
    return access(sock, F_OK) == 0;
}

/* A ponte está habilitada (serviço de usuário) para este uid? */
static gboolean bridge_enabled(guint32 uid) {
    struct passwd *pw = getpwuid(uid);
    if (!pw) return FALSE;
    char path[512];
    snprintf(path, sizeof path,
             "%s/.config/systemd/user/graphical-session.target.wants/anydesk-bridge.service",
             pw->pw_dir);
    return access(path, F_OK) == 0;
}

/* Substitui Type/Display de uma sessão Wayland quando a ponte está ativa. */
static GVariant *rewrite(const char *name, GVariant *v, guint32 uid) {
    char dpy[32];
    if (!name || !v) return v;
    if (strcmp(name, "Type") && strcmp(name, "Display")) return v;
    gboolean is_wayland = !strcmp(name, "Type") && g_variant_is_of_type(v, G_VARIANT_TYPE_STRING) &&
                          !strcmp(g_variant_get_string(v, NULL), "wayland");
    gboolean ready = bridge_display(uid, dpy, sizeof dpy);
    /* O AnyDesk guarda o tipo da sessão na primeira consulta (ex.: logo após o
     * login). Se a ponte está habilitada mas ainda subindo, espera por ela. */
    if (!ready && is_wayland && bridge_enabled(uid)) {
        logf_("uid %u: Type consultado antes da ponte ficar pronta, aguardando", uid);
        for (int i = 0; i < 200 && !ready; i++) {
            g_usleep(100 * 1000);
            ready = bridge_display(uid, dpy, sizeof dpy);
        }
    }
    logf_("uid %u: %s='%s' ponte=%s", uid, name,
          g_variant_is_of_type(v, G_VARIANT_TYPE_STRING) ? g_variant_get_string(v, NULL) : "?",
          ready ? dpy : "inativa");
    if (!ready) return v;
    if (!strcmp(name, "Type") && g_variant_is_of_type(v, G_VARIANT_TYPE_STRING) &&
        !strcmp(g_variant_get_string(v, NULL), "wayland")) {
        logf_("uid %u: Type wayland -> x11", uid);
        g_variant_unref(v);
        return g_variant_ref_sink(g_variant_new_string("x11"));
    }
    if (!strcmp(name, "Display") && g_variant_is_of_type(v, G_VARIANT_TYPE_STRING) &&
        g_variant_get_string(v, NULL)[0] == 0) {
        logf_("uid %u: Display '' -> %s", uid, dpy);
        g_variant_unref(v);
        return g_variant_ref_sink(g_variant_new_string(dpy));
    }
    return v;
}

/* ---- GDBusProxy (proxies gerados do login1) ---- */

typedef GVariant *(*cached_fn)(GDBusProxy *, const gchar *);

static guint32 proxy_uid(GDBusProxy *p, cached_fn real) {
    guint32 uid = (guint32)-1;
    GVariant *u = real(p, "User");
    if (u) {
        if (g_variant_is_of_type(u, G_VARIANT_TYPE("(uo)")))
            g_variant_get(u, "(uo)", &uid, NULL);
        g_variant_unref(u);
    }
    return uid;
}

GVariant *g_dbus_proxy_get_cached_property(GDBusProxy *p, const gchar *name) {
    static cached_fn real;
    if (!real) real = (cached_fn)dlsym(RTLD_NEXT, "g_dbus_proxy_get_cached_property");
    GVariant *v = real(p, name);
    const gchar *iface = g_dbus_proxy_get_interface_name(p);
    if (iface && !strcmp(iface, LOGIND_SESSION) && name &&
        (!strcmp(name, "Type") || !strcmp(name, "Display")))
        v = rewrite(name, v, proxy_uid(p, real));
    return v;
}


/* ---- Chamadas a org.freedesktop.DBus.Properties (Get/GetAll) ----
 * O AnyDesk lê Type via Properties.Get; cobrimos chamadas pela conexão e pelo
 * proxy, síncronas e assíncronas (o resultado é ajustado no *_finish). */

#define PROPS_IFACE "org.freedesktop.DBus.Properties"

typedef GVariant *(*conn_call_sync_fn)(GDBusConnection *, const gchar *, const gchar *,
                                       const gchar *, const gchar *, GVariant *,
                                       const GVariantType *, GDBusCallFlags, gint,
                                       GCancellable *, GError **);

static conn_call_sync_fn real_conn_call_sync(void) {
    static conn_call_sync_fn real;
    if (!real) real = (conn_call_sync_fn)dlsym(RTLD_NEXT, "g_dbus_connection_call_sync");
    return real;
}

typedef struct {
    gboolean getall;
    gchar *prop;            /* Get: nome da propriedade */
    GDBusConnection *conn;
    gchar *dest, *path;
} PropReq;

static void req_free(gpointer p) {
    PropReq *r = p;
    if (!r) return;
    g_free(r->prop);
    g_free(r->dest);
    g_free(r->path);
    if (r->conn) g_object_unref(r->conn);
    g_free(r);
}

/* Reconhece Properties.Get/GetAll de login1.Session. method pode vir como
 * "Get" (com iface separado) ou "org.freedesktop.DBus.Properties.Get". */
static PropReq *req_parse(GDBusConnection *c, const gchar *dest, const gchar *path,
                          const gchar *iface, const gchar *method, GVariant *params) {
    if (!method || !params || !path) return NULL;
    const gchar *m = method;
    if (g_str_has_prefix(method, PROPS_IFACE ".")) m = method + strlen(PROPS_IFACE ".");
    else if (!iface || strcmp(iface, PROPS_IFACE)) return NULL;
    const gchar *want_iface, *want_prop = NULL;
    gboolean getall;
    if (!strcmp(m, "Get") && g_variant_is_of_type(params, G_VARIANT_TYPE("(ss)"))) {
        g_variant_get(params, "(&s&s)", &want_iface, &want_prop);
        getall = FALSE;
        if (strcmp(want_prop, "Type") && strcmp(want_prop, "Display")) return NULL;
    } else if (!strcmp(m, "GetAll") && g_variant_is_of_type(params, G_VARIANT_TYPE("(s)"))) {
        g_variant_get(params, "(&s)", &want_iface);
        getall = TRUE;
    } else {
        return NULL;
    }
    if (strcmp(want_iface, LOGIND_SESSION)) return NULL;
    PropReq *r = g_new0(PropReq, 1);
    r->getall = getall;
    r->prop = g_strdup(want_prop);
    r->conn = c ? g_object_ref(c) : NULL;
    r->dest = g_strdup(dest);
    r->path = g_strdup(path);
    return r;
}

static guint32 req_uid(PropReq *q) {
    guint32 uid = (guint32)-1;
    if (!q->conn) return uid;
    GVariant *r = real_conn_call_sync()(q->conn, q->dest, q->path, PROPS_IFACE, "Get",
                                        g_variant_new("(ss)", LOGIND_SESSION, "User"),
                                        G_VARIANT_TYPE("(v)"), G_DBUS_CALL_FLAGS_NONE, -1,
                                        NULL, NULL);
    if (r) {
        GVariant *inner;
        g_variant_get(r, "(v)", &inner);
        if (g_variant_is_of_type(inner, G_VARIANT_TYPE("(uo)")))
            g_variant_get(inner, "(uo)", &uid, NULL);
        g_variant_unref(inner);
        g_variant_unref(r);
    }
    return uid;
}

/* Recebe a resposta (posse transferida) e devolve a resposta ajustada. */
static GVariant *req_fix(PropReq *q, GVariant *r) {
    if (!q || !r) return r;
    guint32 uid = req_uid(q);
    if (!q->getall && g_variant_is_of_type(r, G_VARIANT_TYPE("(v)"))) {
        GVariant *inner;
        g_variant_get(r, "(v)", &inner);
        GVariant *nv = rewrite(q->prop, inner, uid);
        g_variant_unref(r);
        r = g_variant_ref_sink(g_variant_new("(v)", nv));
        g_variant_unref(nv);
    } else if (q->getall && g_variant_is_of_type(r, G_VARIANT_TYPE("(a{sv})"))) {
        GVariant *dict;
        g_variant_get(r, "(@a{sv})", &dict);
        GVariantBuilder b;
        g_variant_builder_init(&b, G_VARIANT_TYPE("a{sv}"));
        GVariantIter it;
        const gchar *k;
        GVariant *val;
        g_variant_iter_init(&it, dict);
        while (g_variant_iter_next(&it, "{&sv}", &k, &val)) {
            val = rewrite(k, val, uid);
            g_variant_builder_add(&b, "{sv}", k, val);
            g_variant_unref(val);
        }
        g_variant_unref(dict);
        g_variant_unref(r);
        r = g_variant_ref_sink(g_variant_new("(a{sv})", &b));
    }
    return r;
}

static PropReq *req_from_proxy(GDBusProxy *p, const gchar *method, GVariant *params) {
    return req_parse(g_dbus_proxy_get_connection(p), g_dbus_proxy_get_name(p),
                     g_dbus_proxy_get_object_path(p), g_dbus_proxy_get_interface_name(p),
                     method, params);
}

/* Assíncrono: embrulha o callback e anexa o pedido ao GAsyncResult; o
 * *_finish correspondente lê o pedido e ajusta a resposta. */
#define REQ_KEY "anydesk-bridge-req"

typedef struct {
    GAsyncReadyCallback cb;
    gpointer ud;
    PropReq *req;
} AsyncWrap;

static void async_trampoline(GObject *src, GAsyncResult *res, gpointer data) {
    AsyncWrap *w = data;
    g_object_set_data_full(G_OBJECT(res), REQ_KEY, w->req, req_free);
    if (w->cb) w->cb(src, res, w->ud);
    g_free(w);
}

static GVariant *finish_fix(GAsyncResult *res, GVariant *r) {
    PropReq *q = res ? g_object_get_data(G_OBJECT(res), REQ_KEY) : NULL;
    return q ? req_fix(q, r) : r;
}

/* Normaliza params flutuantes para podermos inspecioná-los antes de repassar. */
#define SINK(params) do { if (params) g_variant_ref_sink(params); } while (0)
#define UNSINK(params) do { if (params) g_variant_unref(params); } while (0)

GVariant *g_dbus_connection_call_sync(GDBusConnection *c, const gchar *dest, const gchar *path,
                                      const gchar *iface, const gchar *method, GVariant *params,
                                      const GVariantType *rtype, GDBusCallFlags flags, gint timeout,
                                      GCancellable *cancel, GError **err) {
    SINK(params);
    PropReq *q = req_parse(c, dest, path, iface, method, params);
    GVariant *r = real_conn_call_sync()(c, dest, path, iface, method, params, rtype, flags,
                                        timeout, cancel, err);
    r = req_fix(q, r);
    req_free(q);
    UNSINK(params);
    return r;
}

typedef GVariant *(*conn_call_fd_sync_fn)(GDBusConnection *, const gchar *, const gchar *,
                                          const gchar *, const gchar *, GVariant *,
                                          const GVariantType *, GDBusCallFlags, gint,
                                          GUnixFDList *, GUnixFDList **, GCancellable *,
                                          GError **);

GVariant *g_dbus_connection_call_with_unix_fd_list_sync(
    GDBusConnection *c, const gchar *dest, const gchar *path, const gchar *iface,
    const gchar *method, GVariant *params, const GVariantType *rtype, GDBusCallFlags flags,
    gint timeout, GUnixFDList *fds, GUnixFDList **out_fds, GCancellable *cancel, GError **err) {
    static conn_call_fd_sync_fn real;
    if (!real)
        real = (conn_call_fd_sync_fn)dlsym(RTLD_NEXT, "g_dbus_connection_call_with_unix_fd_list_sync");
    SINK(params);
    PropReq *q = req_parse(c, dest, path, iface, method, params);
    GVariant *r = real(c, dest, path, iface, method, params, rtype, flags, timeout, fds, out_fds,
                       cancel, err);
    r = req_fix(q, r);
    req_free(q);
    UNSINK(params);
    return r;
}

typedef void (*conn_call_fn)(GDBusConnection *, const gchar *, const gchar *, const gchar *,
                             const gchar *, GVariant *, const GVariantType *, GDBusCallFlags,
                             gint, GCancellable *, GAsyncReadyCallback, gpointer);

void g_dbus_connection_call(GDBusConnection *c, const gchar *dest, const gchar *path,
                            const gchar *iface, const gchar *method, GVariant *params,
                            const GVariantType *rtype, GDBusCallFlags flags, gint timeout,
                            GCancellable *cancel, GAsyncReadyCallback cb, gpointer ud) {
    static conn_call_fn real;
    if (!real) real = (conn_call_fn)dlsym(RTLD_NEXT, "g_dbus_connection_call");
    SINK(params);
    PropReq *q = req_parse(c, dest, path, iface, method, params);
    if (q) {
        AsyncWrap *w = g_new0(AsyncWrap, 1);
        w->cb = cb;
        w->ud = ud;
        w->req = q;
        real(c, dest, path, iface, method, params, rtype, flags, timeout, cancel,
             async_trampoline, w);
    } else {
        real(c, dest, path, iface, method, params, rtype, flags, timeout, cancel, cb, ud);
    }
    UNSINK(params);
}

typedef GVariant *(*conn_finish_fn)(GDBusConnection *, GAsyncResult *, GError **);

GVariant *g_dbus_connection_call_finish(GDBusConnection *c, GAsyncResult *res, GError **err) {
    static conn_finish_fn real;
    if (!real) real = (conn_finish_fn)dlsym(RTLD_NEXT, "g_dbus_connection_call_finish");
    return finish_fix(res, real(c, res, err));
}

typedef GVariant *(*proxy_call_sync_fn)(GDBusProxy *, const gchar *, GVariant *, GDBusCallFlags,
                                        gint, GCancellable *, GError **);

GVariant *g_dbus_proxy_call_sync(GDBusProxy *p, const gchar *method, GVariant *params,
                                 GDBusCallFlags flags, gint timeout, GCancellable *cancel,
                                 GError **err) {
    static proxy_call_sync_fn real;
    if (!real) real = (proxy_call_sync_fn)dlsym(RTLD_NEXT, "g_dbus_proxy_call_sync");
    SINK(params);
    PropReq *q = req_from_proxy(p, method, params);
    GVariant *r = real(p, method, params, flags, timeout, cancel, err);
    r = req_fix(q, r);
    req_free(q);
    UNSINK(params);
    return r;
}

typedef GVariant *(*proxy_call_fd_sync_fn)(GDBusProxy *, const gchar *, GVariant *,
                                           GDBusCallFlags, gint, GUnixFDList *, GUnixFDList **,
                                           GCancellable *, GError **);

GVariant *g_dbus_proxy_call_with_unix_fd_list_sync(GDBusProxy *p, const gchar *method,
                                                   GVariant *params, GDBusCallFlags flags,
                                                   gint timeout, GUnixFDList *fds,
                                                   GUnixFDList **out_fds, GCancellable *cancel,
                                                   GError **err) {
    static proxy_call_fd_sync_fn real;
    if (!real)
        real = (proxy_call_fd_sync_fn)dlsym(RTLD_NEXT, "g_dbus_proxy_call_with_unix_fd_list_sync");
    SINK(params);
    PropReq *q = req_from_proxy(p, method, params);
    GVariant *r = real(p, method, params, flags, timeout, fds, out_fds, cancel, err);
    r = req_fix(q, r);
    req_free(q);
    UNSINK(params);
    return r;
}

typedef void (*proxy_call_fn)(GDBusProxy *, const gchar *, GVariant *, GDBusCallFlags, gint,
                              GCancellable *, GAsyncReadyCallback, gpointer);

void g_dbus_proxy_call(GDBusProxy *p, const gchar *method, GVariant *params, GDBusCallFlags flags,
                       gint timeout, GCancellable *cancel, GAsyncReadyCallback cb, gpointer ud) {
    static proxy_call_fn real;
    if (!real) real = (proxy_call_fn)dlsym(RTLD_NEXT, "g_dbus_proxy_call");
    SINK(params);
    PropReq *q = req_from_proxy(p, method, params);
    if (q) {
        AsyncWrap *w = g_new0(AsyncWrap, 1);
        w->cb = cb;
        w->ud = ud;
        w->req = q;
        real(p, method, params, flags, timeout, cancel, async_trampoline, w);
    } else {
        real(p, method, params, flags, timeout, cancel, cb, ud);
    }
    UNSINK(params);
}

typedef GVariant *(*proxy_finish_fn)(GDBusProxy *, GAsyncResult *, GError **);

GVariant *g_dbus_proxy_call_finish(GDBusProxy *p, GAsyncResult *res, GError **err) {
    static proxy_finish_fn real;
    if (!real) real = (proxy_finish_fn)dlsym(RTLD_NEXT, "g_dbus_proxy_call_finish");
    return finish_fix(res, real(p, res, err));
}
