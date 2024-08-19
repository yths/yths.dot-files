#!/bin/bash
ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime
timedatectl set-ntp true
hwclock --systohc
# uncomment en_US.UTF-8 UTF-8 (and other needed locales) and generate locales
sed -i 's/#en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen
locale-gen
echo "LANG=en_US.UTF-8" > /etc/locale.conf
echo "KEYMAP=de-latin1" > /etc/vconsole.conf
# configure hostname (replace nippur by desired hostname)
echo "nippur" > /etc/hostname
echo "127.0.0.1 localhost" > /etc/hosts
echo "::1 localhost" >> /etc/hosts
echo "127.0.1.1 nippur.localdomain nippur" >> /etc/hosts

# set root password (replace password by the desired root password)
echo "root:password" | chpasswd

# install bootloader
bootctl --path=/boot install
echo "timeout 4" > /boot/loader/loader.conf
echo "default arch" >> /boot/loader/loader.conf

# install essential packages
pacman-key --init
pacman-key --populate
pacman -S --noconfirm efibootmgr reflector rsync tmux git
# change the country to the one you are in
reflector --country DE --sort rate --save /etc/pacman.d/mirrorlist
# enable services
systemctl enable systemd-boot-update.service
systemctl enable systemd-timesyncd.service
systemctl enable systemd-resolved.service
systemctl enable iwd
systemctl enable dhcpcd
systemctl enable sshd
systemctl enable bluetooth
systemctl enable reflector.timer

# create user with sudo privileges (replace username and password by the desired values)
useradd -m -g users -G wheel -s /bin/bash yths
echo "yths:password" | chpasswd
# allow members of wheel group to execute any command as root
sed -i 's/# %wheel ALL=(ALL:ALL) ALL/%wheel ALL=(ALL:ALL) ALL/' /etc/sudoers
