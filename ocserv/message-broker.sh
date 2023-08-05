#!/usr/bin/env bash

PASSWD=/tmp/ocserv/passwd
OCCTL_SOCK=/tmp/ocserv/occtl.sock

function is_exist() {
    grep --quiet "^$1:.*" $PASSWD
}

function add_user() {
    is_exist $1 && return 3
    ocpasswd --passwd $PASSWD $1 <<< ${2}$'\n'${2}
}

function delete_user() {
    ! is_exist $1 && return 4
    occtl --socket-file $OCCTL_SOCK disconnect user $1 &>/dev/null
    ocpasswd --passwd $PASSWD --delete $1
}

function show_user() {
    occtl --debug --json --socket-file $OCCTL_SOCK show user $1
}

function show_users() {
    occtl --debug --json --socket-file $OCCTL_SOCK show users
}

function show_status() {
    occtl --debug --json --socket-file $OCCTL_SOCK show status
}

STDIN=$(cat)
STDOUT=$($STDIN)
echo -n "$?$STDOUT"
