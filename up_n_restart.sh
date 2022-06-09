#!/bin/bash

git stash
git fetch
git rebase
git stash pop

pkill -f 'sc.py'
(./sc.py -d "$(grep destination_email cfg.json | sed 's/^.*://' | sed 's/[ ",]*//g')" &)
