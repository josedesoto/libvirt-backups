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

Name: Name of the domain. Have to be the same as we have call in the libvirt server.
Host: Specify the IP to libvirt 
Order: Specify the priority of the backup
Services: Not mandatory. Info for the email reminder.

Example:
```
doms_to_backup = [
        ["test1", "localhost", 2, "service1, Concluence"],
        ["test1-clone", "localhost", 1, "Hudson"],
        ["test-sparse-file", "10.1.3.110", 1, "Gerrit and svn"],
    ]
```