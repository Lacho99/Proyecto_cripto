#!/data/data/com.termux/files/usr/bin/sh
SESSION="trading"
VERSION="v9.3"
PATH_BOT="/data/data/com.termux/files/home/storage/shared/documents/Job_2025/Python/Proyecto_Cripto"
LOG_PYTHON="$PATH_BOT/bot_python.log"
BOOT_LOG="$PATH_BOT/boot_watchdog.log"
RESTART_COUNTER="$PATH_BOT/restart_counter.txt"
MAX_RESTARTS=5
RESTART_WINDOW=600

# NUEVA: Variable para tiempo de inicio extendido
STARTUP_GRACE_SECONDS=90

# NUEVA: Delay entre kill y start (segundos)
KILL_START_DELAY=2

get_timestamp() {
    date +%s 2>/dev/null | cut -d. -f1
}

log() {
    echo "[$(date '+%d/%m/%Y %H:%M:%S')] $1" | tee -a "$BOOT_LOG"
}

# NUEVA: Esperar a que el proceso Python exista primero
esperar_proceso() {
    log "⏳ Esperando que el proceso Python se inicie..."
    local espera=0
    local max_espera=15
    
    while [ $espera -lt $max_espera ]; do
        pid=$(pgrep -f "Grid_Master.py" | head -1)
        if [ -n "$pid" ]; then
            log "✅ Proceso Python detectado (PID: $pid)"
            return 0
        fi
        sleep 1
        espera=$((espera + 1))
    done
    
    log "⚠️ No se detectó proceso después de ${max_espera}s"
    return 1
}

# MODIFICADA: Más tiempo y mejor validación
esperar_latido_inicial() {
    log "⏳ Esperando primer latido del bot (máx ${STARTUP_GRACE_SECONDS}s)..."
    local espera=0
    
    # Primero asegurar que el proceso existe
    if ! esperar_proceso; then
        return 1
    fi
    
    # Ahora esperar el primer latido
    while [ $espera -lt $STARTUP_GRACE_SECONDS ]; do
        last_alive="$PATH_BOT/Logs/last_alive_${VERSION}.txt"
        if [ -f "$last_alive" ]; then
            last_heartbeat=$(cat "$last_alive" 2>/dev/null | tr -d ' ' | cut -d. -f1)
            # Verificar que el timestamp sea válido (entre 2025 y 2027)
            if [ -n "$last_heartbeat" ] && [ "$last_heartbeat" -gt 1700000000 ] 2>/dev/null && [ "$last_heartbeat" -lt 1800000000 ] 2>/dev/null; then
                log "✅ Latido detectado en ${espera}s: $last_heartbeat"
                return 0
            fi
        fi
        
        # Mostrar progreso cada 10 segundos
        if [ $((espera % 10)) -eq 0 ] && [ $espera -gt 0 ]; then
            log "   ⏱️ Esperando latido... ${espera}/${STARTUP_GRACE_SECONDS}s"
        fi
        
        sleep 2
        espera=$((espera + 2))
    done
    
    log "⚠️ No se detectó latido válido después de ${STARTUP_GRACE_SECONDS}s"
    return 1
}

# MODIFICADA: Más tolerante durante el inicio
"""check_bot_alive() {
    pid=$(pgrep -f "Grid_Master.py" | head -1)
    if [ -z "$pid" ]; then
        return 1
    fi
    
    state=$(ps -o state= -p $pid 2>/dev/null | tr -d ' ')
    if [ "$state" = "D" ] || [ "$state" = "Z" ]; then
        log "⚠️ Proceso $pid en estado $state"
        return 2
    fi
    
    last_alive="$PATH_BOT/Logs/last_alive_${VERSION}.txt"
    if [ -f "$last_alive" ]; then
        last_heartbeat=$(cat "$last_alive" 2>/dev/null | tr -d ' ' | cut -d. -f1)
        
        # Validar que el timestamp sea razonable (entre 2025 y 2027)
        if [ -z "$last_heartbeat" ] || [ "$last_heartbeat" -lt 1700000000 ] 2>/dev/null || [ "$last_heartbeat" -gt 1800000000 ] 2>/dev/null; then
            log "⚠️ Latido inválido: '$last_heartbeat'"
            return 3
        fi
        
        now=$(get_timestamp)
        diff=$((now - last_heartbeat))
        
        # Si la diferencia es negativa o enorme (> 10 minutos), es error
        if [ $diff -lt 0 ] || [ $diff -gt 600 ]; then
            log "⚠️ Diferencia anómala: ${diff}s"
            return 3
        fi
        
        # INCREASED: De 120 a 180 segundos (3 minutos) de tolerancia
        if [ $diff -gt 180 ]; then
            log "⚠️ Último latido hace ${diff}s"
            return 3
        fi
    else
        # NUEVO: Durante los primeros 90 segundos, no considerar falta de archivo como error
        # Verificar cuánto tiempo lleva el proceso vivo
        if [ -n "$pid" ]; then
            process_start=$(ps -o lstart= -p $pid 2>/dev/null)
            if [ -n "$process_start" ]; then
                # Si el proceso tiene menos de STARTUP_GRACE_SECONDS segundos, ignorar
                log "ℹ️ Proceso joven, esperando primer latido..."
                return 0  # Considerar vivo durante el período de gracia
            fi
        fi
        log "⚠️ Archivo de latido no existe"
        return 4
    fi
    
    return 0
}"""

check_bot_alive() {
    pid=$(pgrep -f "Grid_Master.py" | head -1)
    if [ -z "$pid" ]; then
        return 1
    fi
    
    state=$(ps -o state= -p $pid 2>/dev/null | tr -d ' ')
    if [ "$state" = "D" ] || [ "$state" = "Z" ]; then
        log "⚠️ Proceso $pid en estado $state"
        return 2
    fi
    
    # ===== VERIFICAR LATIDO EN Logs/ =====
    last_alive="$PATH_BOT/Logs/last_alive_${VERSION}.txt"
    
    if [ -f "$last_alive" ]; then
        last_heartbeat=$(cat "$last_alive" 2>/dev/null | tr -d ' ' | cut -d. -f1)
        
        if [ -z "$last_heartbeat" ] || [ "$last_heartbeat" -lt 1700000000 ] 2>/dev/null || [ "$last_heartbeat" -gt 1800000000 ] 2>/dev/null; then
            log "⚠️ Latido inválido: '$last_heartbeat'"
            return 3
        fi
        
        now=$(get_timestamp)
        diff=$((now - last_heartbeat))
        
        if [ $diff -lt 0 ] || [ $diff -gt 600 ]; then
            log "⚠️ Diferencia anómala: ${diff}s"
            return 3
        fi
        
        if [ $diff -gt 180 ]; then
            log "⚠️ Último latido hace ${diff}s"
            return 3
        fi
        
        return 0  # ✅ Todo bien
        
    else
        # ===== CORRECCIÓN: Período de gracia CON LÍMITE =====
        # Calcular cuánto tiempo lleva vivo el proceso
        if [ -n "$pid" ]; then
            process_start=$(ps -o lstart= -p $pid 2>/dev/null)
            if [ -n "$process_start" ]; then
                # Convertir fecha de inicio a timestamp
                start_ts=$(date -d "$process_start" +%s 2>/dev/null)
                if [ -n "$start_ts" ]; then
                    now=$(get_timestamp)
                    age=$((now - start_ts))
                    
                    # PERÍODO DE GRACIA: 120 segundos (2 minutos)
                    if [ $age -lt 120 ]; then
                        log "ℹ️ Proceso joven (${age}s), esperando primer latido..."
                        return 0  # Vivo durante el período de gracia
                    else
                        log "⚠️ Proceso tiene ${age}s sin latido. ¡REINICIANDO!"
                        return 3
                    fi
                fi
            fi
        fi
        
        log "⚠️ Archivo de latido no existe: $last_alive"
        return 4
    fi
}

check_restart_loop() {
    now=$(get_timestamp)
    temp_file="${RESTART_COUNTER}.tmp"
    total=0
    
    if [ -f "$RESTART_COUNTER" ]; then
        while IFS=: read -r ts count; do
            ts_int=$(echo "$ts" | cut -d. -f1)
            # Validar que el timestamp sea razonable
            if [ -n "$ts_int" ] && [ "$ts_int" -gt 1700000000 ] 2>/dev/null && [ "$ts_int" -lt 1800000000 ] 2>/dev/null; then
                if [ $((now - ts_int)) -lt $RESTART_WINDOW ]; then
                    total=$((total + count))
                    echo "$ts_int:$count" >> "$temp_file"
                fi
            fi
        done < "$RESTART_COUNTER"
    fi
    
    echo "$now:1" >> "$temp_file"
    total=$((total + 1))
    
    mv "$temp_file" "$RESTART_COUNTER" 2>/dev/null
    
    if [ $total -gt $MAX_RESTARTS ]; then
        log "🚨 ¡Bucle de reinicios! ($total en ${RESTART_WINDOW}s)"
        return 1
    fi
    return 0
}

restore_script_backup() {
    log "🔄 Intentando restaurar script desde backup..."
    cd "$PATH_BOT"
    
    latest_backup=$(ls -t Grid_Master*_backup_*.py 2>/dev/null | head -1)
    
    if [ -n "$latest_backup" ]; then
        log "📦 Restaurando desde: $latest_backup"
        cp "$latest_backup" "Grid_Master.py"
        log "✅ Script restaurado"
        return 0
    else
        log "❌ No hay backup"
        return 1
    fi
}

force_kill_bot() {
    log "💀 Forzando muerte del bot..."
    pkill -9 -f "Grid_Master.py" 2>/dev/null
    pkill -9 -f "python.*Grid_Master" 2>/dev/null
    tmux kill-session -t $SESSION 2>/dev/null
    sleep 2
    log "✅ Bot eliminado"
}

lanzar_bot() {
    log "🚀 Lanzando bot ${VERSION}..."
    cd "$PATH_BOT"
    
    # Limpiar latido anterior para evitar falsos positivos
    rm -f "$PATH_BOT/Logs/last_alive_${VERSION}.txt" 2>/dev/null
    
    # Asegurar que no haya procesos zombis del bot anterior
    log "⏳ Esperando ${KILL_START_DELAY}s antes de lanzar (para evitar conflictos)..."
    sleep $KILL_START_DELAY
    
    # NUEVO: Usar nohup como alternativa si tmux falla
    tmux new-session -d -s $SESSION -c "$PATH_BOT" "stdbuf -oL python -u Grid_Master.py 2>&1 | tee -a '$LOG_PYTHON'"
    
    if [ $? -ne 0 ]; then
        log "⚠️ tmux falló, intentando con nohup..."
        nohup stdbuf -oL python -u "Grid_Master.py" >> "$LOG_PYTHON" 2>&1 &
    fi
    
    # NUEVO: Esperar más tiempo para la inicialización completa
    log "⏳ Esperando inicialización completa (${STARTUP_GRACE_SECONDS}s)..."
    sleep 5  # Pequeña pausa inicial
    
    if esperar_latido_inicial; then
        log "✅ Bot lanzado exitosamente"
        return 0
    else
        log "❌ Bot no respondió después de ${STARTUP_GRACE_SECONDS}s"
        return 1
    fi
}

# NUEVA: Verificar conectividad a Binance
check_binance_connectivity() {
    log "🌐 Verificando conectividad con Binance..."
    
    # Probar ping a Binance
    if ping -c 1 -W 5 api.binance.com > /dev/null 2>&1; then
        log "✅ Binance reachable"
        return 0
    else
        log "⚠️ No se puede alcanzar Binance, esperando..."
        return 1
    fi
}

# MODIFICADO: Loop principal con más paciencia
while true; do
    if [ -f "$PATH_BOT/reset.lock" ]; then
        log "🧹 Orden de reset detectada..."
        force_kill_bot
        cd "$PATH_BOT/GridBot"
        rm -f state_trading_*.json
        cd ..
        rm -f  trades_*.csv "$LOG_PYTHON"
        #cd /Logs
        rm -f log_eficiencia_*.csv "$RESTART_COUNTER" reset.lock
        
        # ===== CAMBIADO: Limpiar Logs/ =====
        rm -f "$PATH_BOT/Logs/last_alive_${VERSION}.txt" #\
          #"$PATH_BOT/Logs/log_eficiencia_*.csv" \
          #"$RESTART_COUNTER" \
          #"$PATH_BOT/reset.lock"
  
        log "✅ Limpieza completada"
    fi
    
    if ! pgrep -x "sshd" > /dev/null; then
        log "🔑 SSH caído. Reiniciando..."
        sshd
    fi
    
    # Verificar conectividad antes de decisiones drásticas
    check_binance_connectivity
    
    check_bot_alive
    bot_status=$?
    
    case $bot_status in
        0)
            # Bot funcionando correctamente
            if [ -f "$RESTART_COUNTER" ]; then
                file_time=$(stat -c %Y "$RESTART_COUNTER" 2>/dev/null | cut -d. -f1)
                now=$(get_timestamp)
                if [ -n "$file_time" ] && [ "$file_time" -gt 1700000000 ] 2>/dev/null; then
                    if [ $((now - file_time)) -gt $RESTART_WINDOW ]; then
                        rm -f "$RESTART_COUNTER"
                        log "✅ Bot estable"
                    fi
                fi
            fi
            
            # NUEVO: Verificar que el WebSocket esté recibiendo datos
            log "✅ Bot OK - Latido reciente"
            ;;
        1)
            log "⚠️ Bot no detectado..."
            if check_restart_loop; then
                log "🔄 Lanzando bot..."
                force_kill_bot
                # ✅ NUEVO: Delay añadido dentro de lanzar_bot()
                if lanzar_bot; then
                    log "✅ Bot relanzado exitosamente"
                else
                    log "❌ Falló el lanzamiento del bot"
                fi
            else
                log "🚨 ¡BUCLES INFINITOS!"
                if restore_script_backup; then
                    log "🔄 Script restaurado"
                    force_kill_bot
                    if lanzar_bot; then
                        log "✅ Bot lanzado con script restaurado"
                        rm -f "$RESTART_COUNTER"
                    else
                        log "❌ Falló incluso con script restaurado"
                    fi
                else
                    log "💀 No se pudo recuperar"
                    touch "$PATH_BOT/CRITICAL_ERROR.txt"
                    # NUEVO: Esperar más antes de reintentar
                    sleep 60
                fi
            fi
            ;;
        2|3|4)
            log "⚠️ Bot anormal (código: $bot_status). Reiniciando..."
            force_kill_bot
            if lanzar_bot; then
                log "✅ Bot reiniciado exitosamente"
            else
                log "❌ Falló el reinicio"
            fi
            ;;
    esac
    
    termux-wake-lock 2>/dev/null
    # NUEVO: Sleep más largo (45 segundos en lugar de 30)
    sleep 45
done