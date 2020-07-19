#!/bin/bash

git stash
git fetch
git rebase
git stash pop

sudo pkill -f 'sc.py'
(sudo ./sc.py -d 'XXXXX@gmail.com' &)
