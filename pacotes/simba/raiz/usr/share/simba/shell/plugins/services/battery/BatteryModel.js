function batteryPercentage(device) {
  if (!device || !device.isPresent) return -1
  return Math.round(Number(device.percentage || 0) * 100)
}

function isDischarging(device, onBattery, dischargingState) {
  return !!(device && device.isPresent && onBattery && device.state === dischargingState)
}

function shouldWarnLowBattery(device, onBattery, dischargingState, threshold, lastNotifiedTier) {
  var level = batteryPercentage(device)
  if (level < 0) return { level: level, notify: false, newTier: 0, notifiedLowBattery: false }

  var discharging = isDischarging(device, onBattery, dischargingState)
  if (!discharging || level > 20) {
    return { level: level, notify: false, newTier: 0, notifiedLowBattery: false }
  }

  // Tiers de alerta:
  // 3 = emergência (<= 2%) -> suspensão para proteger dados
  // 2 = crítica (<= 5%)    -> alerta urgente sonoro e visual
  // 1 = baixa (<= 15%)     -> aviso sutil para plugar o carregador
  var currentTier = level <= 2 ? 3 : (level <= 5 ? 2 : (level <= 15 ? 1 : 0))

  var previous = typeof lastNotifiedTier === "number" ? lastNotifiedTier : (lastNotifiedTier ? 1 : 0)

  if (currentTier > previous) {
    return {
      level: level,
      notify: true,
      newTier: currentTier,
      notifiedLowBattery: true
    }
  }

  return {
    level: level,
    notify: false,
    newTier: previous,
    notifiedLowBattery: currentTier > 0
  }
}

if (typeof module !== "undefined") {
  module.exports = {
    batteryPercentage: batteryPercentage,
    isDischarging: isDischarging,
    shouldWarnLowBattery: shouldWarnLowBattery
  }
}
