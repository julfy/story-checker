#!/bin/bash

show_help() {
  echo "Mandatory Args:"
  echo -e "-r\t Pull changes and start or restart if running" | expand -t 30
  echo -e "-s\t Stop" | expand -t 30
  exit 1
}

function start () {
    git stash
    git fetch
    git rebase
    git stash pop
    (./sc.py -d "$(grep destination_email cfg.json | sed 's/^.*://' | sed 's/[ ",]*//g')" &)
}

function stop () {
    pkill -f 'sc.py'
}

for i in "$@"; do
  case ${i} in
      -r*)
          stop
          start
          shift
          ;;
      -s*)
          stop
          shift
          ;;
      *)
          show_help
          ;;
  esac
done
