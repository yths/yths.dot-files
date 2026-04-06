#
# ~/.bashrc
#

# If not running interactively, don't do anything
[[ $- != *i* ]] && return

# start tmux
if command -v tmux &> /dev/null && [ -n "$PS1" ] && [[ $DISPLAY ]] && [[ ! "$TERM" =~ screen ]] && [[ ! "$TERM" =~ tmux ]] && [ -z "$TMUX" ]; then
  exec tmux new-session -A -s $HOSTNAME
fi

## start tmux if sshing into the computer
#if [[ $- =~ i ]] && [[ -z "$TMUX" ]] && [[ -n "$SSH_TTY" ]]; then
#  tmux attach-session -t ssh_tmux  || tmux new-session -s ssh_tmux
#fi

source ~/.dircolors
alias ls='ls --color=auto'
alias grep='grep --color=auto'
alias bambustudio='flatpak run com.bambulab.BambuStudio'
alias code='code --enable-proposed-api ms-python.python --enable-proposed-api ms-python.debugpy --enable-proposed-api GitHub.copilot'
alias kubectl="minikube kubectl --"

alias yay-drop-caches='sudo paccache -rk3; yay -Sc --aur --noconfirm'
alias yay-update-all='export TMPFILE="$(mktemp)"; \
    sudo true; \
    rate-mirrors --entry-country=DE --save=$TMPFILE arch --max-delay=21600 \
      && sudo mv /etc/pacman.d/mirrorlist /etc/pacman.d/mirrorlist-backup \
      && sudo mv $TMPFILE /etc/pacman.d/mirrorlist \
      && yay-drop-caches \
      && yay -Syyu --noconfirm'


PS1='[\u@\h \W]\$ '
eval "$(starship init bash)"
