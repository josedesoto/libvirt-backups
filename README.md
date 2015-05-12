# libvirt-backups


The python script have been developed to:

0. Perform a backup the last Sunday on the month
0. Notify to staff about the backup and estimation time of the down services 3 days before (Thursdays)
0. To Perform all the backups using libvirt and scp command.

After a backup the result will be:

0. One new folder with the domain server name
0. Inside each folder, we will have each virtual disk and the .xml file with the hypervisor configuration

## Parameter to configure in the script

To specify the emails or the list where to send the errors:
```
LIB_VIRT_ERROR_EMAIL_LIST=['']
```

To specify the emails or the list where to send the reminder
```
NOTIFY_BACKUP_EMAIL_LIST=['']
```

If you need to specify more than one email: ['example@example.com','example2@example.com']

To specify the user and the pass of the libvirt servers:
```
SASL_USER = "fred"
SASL_PASS = "temporal"
```

To make the calculation of the estimation. This values is a estimation and be taken with a scp test from your backup server to the domains servers: 
```
SPEED_NET=30 #MB
```

Path where we want to backup the VPS. Make sure you have enough space:
```
backpath='/home/jose/TMP/BACKVIR'
```

Setup how many days before the backup system will send a reminder email:
```
REMINDER_DAYS_BACKUP=3
```

To specify the list of the domains we want to backup. The contains 4 variables:

* Name: Name of the domain. Have to be the same as we have call in the libvirt server.
* Host: Specify the IP to libvirt 
* Order: Specify the priority of the backup
* Services: Not mandatory. Info for the email reminder.

Example:
```
doms_to_backup = [
        ["test1", "localhost", 2, "service1, Concluence"],
        ["test1-clone", "localhost", 1, "Hudson"],
        ["test-sparse-file", "10.1.3.110", 1, "Gerrit and svn"],
    ]
```

## 1.1 Configure TCP for libvirtd
### Ubuntu

Configuration file: /etc/default/libvirt-bin
```
libvirtd_opts="-d -l"
```

In the configuration file: /etc/libvirt/libvirtd.conf
```
listen_tls = 0
listen_tcp = 1
tcp_port = "16509"
auth_tcp = "none"
```

With this option we will have enable a new port where we can do the new connections to the server:
```
jose@:~$ sudo netstat -anp | grep libvir 
tcp        0      0 0.0.0.0:16509           0.0.0.0:*               LISTEN      1231/libvirtd
```

To this port everyone can connect. So, it is not save. At least in a trust network we need to have authentications. For now we can skip the encryption.

To install authentication, we need to install: SASL is the Simple Authentication and Security Layer, 
```
sudo apt-get install sasl2-bin 
```

####Manage users:

To add a user:
```
sudo saslpasswd2 -a libvirt backup
```

To list the users:
```
sudo sasldblistusers2 -f /etc/libvirt/passwd.db
```

To delete the user:
```
sudo saslpasswd2 -a libvirt -d backup
```

(This step does not need to be applied in Centos) In /etc/sasl2/libvirt.conf we have to be sure to have enable mech_list: digest-md5 and in /etc/libvirt/libvirtd.conf to have auth_tcp = "sasl".

####Test:
```
virsh -c qemu+tcp://YOUR_DOMAIN/system list
virsh -c qemu+tcp://YOUR_DOMAIN/system start test1
```
If in both cases virsh should ask for authentication. Introducing the user we have add with  saslpasswd2 command we should perform the action we want.



####Centos:
```
Configuration file: /etc/sysconfig/libvirtd
LIBVIRTD_ARGS="--listen"
```

In the configuration file: /etc/libvirt/libvirtd.conf
```
listen_tls = 0
listen_tcp = 1
tcp_port = "16509"
```

For testing:
```
auth_tcp = "none" (for no auth, just for tetsing)
```

In our case, we will use auth:
```
auth_tcp = "sasl"
```

We have to restart /etc/init.d/libvirtd process. This is libvirt libraries, so not impact over the running VPS.

To allow iptable to connects to the port 16509, we add to /etc/sysconfig/iptables:
```
-A INPUT -m state --state NEW -m tcp -p tcp --dport 16509 -j ACCEPT

/etc/init.d/iptables restart
/etc/init.d/libvirtd reload #To reload the iptables for LIBVIRTD
```

For the authentication look on ubuntu configuration. Cantos by default have installed the sasl2-bin. So, we don't need to install it.