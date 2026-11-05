# Compila contra os cabeçalhos do Hyprland instalado (/usr/include/hyprland).
CXX ?= g++
ifeq ($(CXX),g++)
    EXTRA = --no-gnu-unique
endif
CXXFLAGS ?= -O2
CXXFLAGS += -shared -fPIC -std=c++2b -Wno-c++11-narrowing -Wall -Wno-unused-variable
INCLUDES = `pkg-config --cflags pixman-1 libdrm hyprland libinput libudev wayland-server xkbcommon cairo lua`
SRC = src/main.cpp src/barra.cpp
OUT ?= build/janelas.so

all: $(OUT)

$(OUT): $(SRC) src/janelas.hpp src/barra.hpp src/compat.hpp
	mkdir -p $(dir $(OUT))
	$(CXX) $(CXXFLAGS) $(EXTRA) $(INCLUDES) $(SRC) -o $@.tmp && mv $@.tmp $@

clean:
	rm -rf build
.PHONY: all clean
