#!/bin/bash

git stash
git fetch
git rebase
git stash pop

pkill -f 'sc.py'
(./sc.py -d 'XXXXX@gmail.com' &)
