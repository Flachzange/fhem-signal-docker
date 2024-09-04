#!/bin/bash
#$Id:$

SCRIPTVERSION="0.1"
# Author: Holoarts
# License: GPL
#start script for signal-cli within fhem docker



service dbus start
echo -n "Waiting for dbus to become ready."
    WAIT="service dbus status | grep -i 'dbus is running'"
    echo $WAIT
    CHECK=`$WAIT`
		while [ -z "$CHECK" ]
		do
			echo -n "."
			sleep 1
            CHECK=`$WAIT`
            echo $CHECK
		done
	echo "($CHECK), running"

echo "Setting path"
sudo tee -a  /etc/profile.d/jdk21.sh<<EOF
export JAVA_HOME=/opt/java
export PATH=\$PATH:\$JAVA_HOME/bin
EOF
#export JAVA_HOME=/opt/java
#export PATH=$PATH:$JAVA_HOME/bin
echo "JAVA HOME: " $JAVA_HOME 
echo "Starting signal_cli"
chown fhem.fhem /var/lib/signal-cli                               
sudo -i -u fhem /opt/signal/bin/signal-cli --config /var/lib/signal-cli daemon --system  >>/var/log/signal.log 2>>/var/log/signal.err &
echo -n "Waiting for signal-cli to become ready."
    WAIT='grep -i "Started DBus server on SYSTEM bus" /var/log/signal.err' 
   CHECK=`grep -i "Started DBus server on SYSTEM bus" /var/log/signal.err`
		while [ -z "$CHECK" ]
		do
			echo -n "."
			sleep 1
            CHECK=`grep -i "Started DBus server on SYSTEM bus" /var/log/signal.err`
		done
	echo "($CHECK), running"

 
 


