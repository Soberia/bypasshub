#!/usr/bin/env sh

while true; do
    if [ ! -f /dev/shm/exited ]; then
        if [ -f /dev/shm/exit-code ]; then
            touch /dev/shm/exited
            exit $(< /dev/shm/exit-code)
        fi
        sleep 0.1
        continue
    fi
    rm /dev/shm/exited
    sleep 9000000000
    exit
done
