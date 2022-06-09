Will periodically check the list of web novels and send a notification email in case of update.

Really, anything-checker, if provided with a link and a parser.

Usage:

`./sc.py` - to run once and initialize the history

`(./sc.py -d <email> &)` - to run in loop and detach the process

`./up_n_restart.sh` - fetch updates and restart the checker loop

Setup:
1. `sudo apt install msmtp libsecret-tools`
2. https://github.com/tenllado/dotfiles/tree/master/config/msmtp#the-oauth2-credentials
3. populate cfg.json
4. update /etc/msmtprc with
```
# Set default values for all following accounts.
defaults
host smtp.gmail.com
port 587
protocol smtp
tls on
tls_trust_file /etc/ssl/certs/ca-certificates.crt

account sc-gmail
auth oauthbearer
from <gmail account email, must match gmail_account value in cfg.json>
user <account name, whatever you want>
passwordeval /home/ubuntu/story-checker/oauth2refresh

# Set a default account
account default : sc-gmail
```

5. `sudo ln -s /etc/apparmor.d/usr.bin.msmtp /etc/apparmor.d/disable/`

   `sudo apparmor_parser -R /etc/apparmor.d/usr.bin.msmtp`
