if [ "$HOSTNAME" = "assur" ]; then
    xrandr --output HDMI-1 --primary
    xrandr --output HDMI-0 --right-of HDMI-1 --mode 1920x1080 --filter bilinear --scale-from 3840x2160
    dispwin -d 1 -i /home/yths/.config/icc_profiles/SamsungHD.icc 
    dispwin -d 2 -i /home/yths/.config/icc_profiles/SamsungV2.icc 
fi

if [ "$HOSTNAME" = "nippur" ]; then
    xrandr --output DP-2 --primary
    dispwin -d 1 -i /home/yths/.config/icc_profiles/HP.icc
fi