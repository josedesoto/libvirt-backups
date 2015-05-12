'''
Created on Apr 10, 2013

The python script have been developed to:
  1. Perform a backup the last Sunday on the month
  2. Notify to staff about the backup and estimation time of the down services 3 days before (Thursdays)
  3. To Perform all the backups using libvirt and scp command.

After a backup the result will be:
  1. One new folder with the domain server name
  2. Inside each folder, we will have each virtual disk and the .xml file with the hypervisor configuration

Example crontab:

#Full VPN backup using libvirt.
00 09 * * * /usr/bin/python /opt/app/scripts/virBackup.py >> /dev/null

Depencencies:
apt-get install python-libvirt

'''

import libvirt
import syslog
from xml import dom
import subprocess
from os import path
from re import findall
from time import sleep
import os
import datetime as dt
import sys


LIB_VIRT_ERROR_EMAIL_LIST=['example@gexample.com']
NOTIFY_BACKUP_EMAIL_LIST=['example@gexample.com']

try:
    from operator import methodcaller
except ImportError:
    def methodcaller(name, *args, **kwargs):
        def caller(obj):
            return getattr(obj, name)(*args, **kwargs)
        return caller

class Domfetcher(object):
    """Abstract libvirt API, supply methods to return dom object lists"""
    def __init__(self, SASL_USER, SASL_PASS, uri = None):
        """Connect to hypervisor uri with read write access"""
        # register logit as the error handler
        
        libvirt.registerErrorHandler( logit, 'libvirt error' ) 
    
        try:
            #Without auht
            #self.c = libvirt.open( uri )
            
            #With auth (SASL2)
            self.auth = [[libvirt.VIR_CRED_AUTHNAME, libvirt.VIR_CRED_PASSPHRASE], Domfetcher.request_cred, None]
            self.c = libvirt.openAuth(uri, self.auth, 0)
            
        except:
            self.c = None
            logit( "libvirt error", "Failed to open connection to the hypervisor" )
      
    @staticmethod      
    def request_cred(credentials, user_data):
        for credential in credentials:
            if credential[0] == libvirt.VIR_CRED_AUTHNAME:
                credential[4] = SASL_USER
            elif credential[0] == libvirt.VIR_CRED_PASSPHRASE:
                credential[4] = SASL_PASS
        return 0
            

    def get_all_doms(self):
        """Return a list of running and shutoff dom objects"""
        doms = self.get_running_doms()
        for name in self.get_shutoff_doms():
            doms.append(name)
        return doms

    def get_running_doms(self):
        """Return a list of running dom objects"""
        doms = []
        for id in self.c.listDomainsID(): # loop over the running ids
            dom = self.c.lookupByID( id ) # fetch dom object by id
            if 'Domain-' not in dom.name(): # prevent actions on the Xen hypervisor
                doms.append( dom ) # append dom object to doms
        return doms
    
    def get_shutoff_doms(self):
        """Return a list of all shutoff but defined dom objects"""
        return [self.c.lookupByName( name ) for name in self.c.listDefinedDomains()]
    
    def get_backup_dom(self, dom_to_backup):
        """Accept a list of dom, and return Return a list of running dom objects"""
        """The return is order list by the priority number"""

        dom=None
        try:
            print "WE ADD TO THE LIST: " + dom_to_backup[0]
            dom = self.c.lookupByName( dom_to_backup[0] )
        except:
            logit( "libvirt error", "Failed to open a dom. Review the dom backup list" )
            
 
        return dom
            
    def get_disk_size(self, dom ):
        """Accept a  dom objects, return int with the size disk in MB"""
        xml = dom.XMLDesc( 0 )
        total_size=0
        for disk_path in findall( "<source file='(.*)'/>\n", xml ):
            try:
                #Size in GB
                total_size=total_size + int(self.c.storageVolLookupByPath(disk_path).info()[2]/1024/1024)
            except:
                logit( "libvirt error", "Failed to open one disk when getting size, please add this disk into the POOL " + disk_path)
        
        return total_size
    
    '''
    conn=libvirt.open("qemu:///system")
    list_storage_pool=conn.listStoragePools()
    pool_obj = conn.storagePoolLookupByName('default')
    disk_obj=pool_obj.storageVolLookupByName('test1.img')
    int(pool_obj.storageVolLookupByName('test1.img').info()[2]/1024/1024)
    '''
        

def invoke( dom, method ):
    """Pattern to invoke shutdown, destroy, and start on a  doms"""
    f = methodcaller( method )
    try:
        logit( method, 'invoking %s on %s' % (method, dom.name()) )
        retcode = f(dom)
        if retcode: # log retcode
            logit( 
                  method,
                  '{0} returned {1} on {2}'.format( method, retcode, dom.name() )
                ) 
    except libvirt.libvirtError:
        pass
        
        
def logit( context, message, quiet = False ):
    """syslog and error handler"""
    
    #Only if there is a error we send the email
    if context == "libvirt error":
        mail(message, context, LIB_VIRT_ERROR_EMAIL_LIST)
    
    if type( message ) is tuple:
        message = message[2] # libvirt message is a tuple

    if quiet: pass 
    else: print context + ': ' +  message

    syslog.openlog( 'virt-back', 0, syslog.LOG_LOCAL3 )
    syslog.syslog( message )
    syslog.closelog()
    
    
        
def info( doms ):
    """Accept a list of dom objects, attempt to display info for all"""
    if check_all_running( doms ): print "NOTE: All guests are running"
    if check_all_shutoff( doms ): print "NOTE: All guests are shut off"
    
    
    
    print ''
    print 'running guests: ' + ', '.join( [ dom.name() for dom in get_all_running( doms ) ] )
    print 'shutoff guests: ' + ', '.join( [ dom.name() for dom in get_all_shutoff( doms ) ] )
    print ''
    print 'DomName'.ljust(16) + 'Memory MB'.rjust(12) + 'vCPUs'.rjust(8) + 'CPUtime ms'.rjust(18) + 'State'.rjust(20)
    print '=========================================================================='
    for dom in doms:
        name = dom.name()
        rams = str(dom.info()[2]/1024) + '/' + str(dom.info()[1]/1024)
        cpus = str(dom.info()[3])
        time = str(dom.info()[4]/1000000)
        state = get_status(dom)
        print name.ljust(16) + rams.rjust(12) + cpus.rjust(8) + time.rjust(18) + state.rjust(20)


def check_all_running( doms ):
    """Accept a list of dom objects, check if all guest dom are active"""
    if sum( [dom.isActive() for dom in doms] ) == len( doms ):
        return True
    return False

def check_all_shutoff( doms ):
    """Accept a list of dom objects, check if all guest dom are shut off"""
    if sum( [dom.isActive() for dom in doms] ):
        return False
    return True

    
def get_status( dom ):
    """Accept a dom object, return a string with the current domain status"""
    states = {
        libvirt.VIR_DOMAIN_NOSTATE: 'no state',
        libvirt.VIR_DOMAIN_RUNNING: 'running',
        libvirt.VIR_DOMAIN_BLOCKED: 'blocked on resource',
        libvirt.VIR_DOMAIN_PAUSED: 'paused',
        libvirt.VIR_DOMAIN_SHUTDOWN: 'being shut down',
        libvirt.VIR_DOMAIN_SHUTOFF: 'shut off',
        libvirt.VIR_DOMAIN_CRASHED: 'crashed',
    }
    
    return states.get(dom.info()[0])

def isPause( dom ):
    """Accept a dom objects, check if the guest dom is pause. True=Pause"""
    if dom.info()[0] != 3:
        return False
    return True

def isRunning( dom ):
    """Accept a dom objects, check if the guest dom is Running. True=Pause"""
    if dom.info()[0] != 1:
        return False
    return True


def get_all_running( doms ):
    """Accept a list of dom objects, return a list of running dom objects"""
    return [ dom for dom in doms if dom.isActive() ]

def get_all_shutoff( doms ):
    """Accept a list of dom objects, return a list of shutoff dom objects"""
    return [ dom for dom in doms if not dom.isActive() ]

def scp(source, server, path = ""):
    """Transfer a source file from the host to local"""
    try:
        subprocess.Popen(["scp", "%s:%s" % (server, source), path+'/']).wait()
    except Exception:
        logit( "libvirt error", "Failed coping the dom" )
        return False
    
    return True

def is_last_sun_of_month():
    today = dt.date.today()
    if get_day_backup() == today:
        return True
    
    return False
        
def get_day_backup(month=None):
    '''Get day backup for the current month. Accept a int month. Return a object date.'''
    '''Day backup is the last Sunday of the month'''
    today = dt.date.today()
    sunday=7
    if month != None:
        next_month = dt.date(today.year, month, 15) + dt.timedelta(days=31)
    else:
        next_month = dt.date(today.year, today.month, 15) + dt.timedelta(days=31)
        
    current_month = dt.date(next_month.year, next_month.month, 1) - dt.timedelta(days=1)
    
    #Sunday = 7... Monday = 1. If the last day of the month is Monday, one day less is Sunday. This is the last Sunday on the month
    if current_month.isoweekday() != sunday:
        days_to_rest=current_month.isoweekday()
        last_sunday_month=current_month - dt.timedelta(days=days_to_rest)
        
    else:
        last_sunday_month=current_month
        
    return last_sunday_month
    
        
def show_calendar_backup():
    '''Print the calendar backup for the current year'''
    today = dt.date.today()
    print "CALENDAR FOR "+ str(today.year)
    for month in 1,2,3,4,5,6,7,8,9,10,11,12:
        print get_day_backup(month)
        
def get_calendar_backup():
    '''return a lis calendar backup for the current year'''
    calendar=[]
    for month in 1,2,3,4,5,6,7,8,9,10,11,12:
        calendar.append(str(get_day_backup(month)))
    return calendar


def mail(txt, subject, to):
    '''Acepts String, String, List'''
    import smtplib

    sender = 'example@gexample.com'
    receivers = to
    
    message = """From: From Operations <example@example.com>
To: To Developers <example@gexample.com
Subject: %s

%s.
""" % (subject, txt)

    try:
        smtpObj = smtplib.SMTP('smtp.example.com')
        smtpObj.sendmail(sender, receivers, message)         
    except Exception:
        logit( "libvirt error", "Failed to send a email" )

    

def backup ( dom, backpath, host ):
    
    before_status=''
    #if dom is running, we paused to make the backup
    if isRunning(dom):
        invoke(dom, 'suspend')
        before_status="running"
        while True:
           if isPause(dom):
               print get_status(dom)
               break
        
        
    #Update the new backpath for each dom
    backpath_dom=backpath+'/'+dom.name()
    
    #we backup the XML file to have the configuration
    if not os.path.exists(backpath_dom):
        try:
            os.makedirs(backpath_dom)
        except:
                logit( "libvirt error", "Failed to create a folder. We skip backup for: " + dom.name() )
                
                
    xml = dom.XMLDesc( 0 )
    
    """
    How to parse the XML. WORKS
    from xml.dom.minidom import parse, parseString
    xml_parse = parseString(xml)
    dom_name=xml_parse.getElementsByTagName("name")[0].firstChild.data
    """
    
    xmlfile = path.join( backpath_dom, dom.name() + '.xml' )
    f = open( xmlfile, 'w')
    f.write( xml )
    f.close()
    disklist = findall( "<source file='(.*)'/>\n", xml )
    
    #We have to copy all the disk for the specific domain
    for disk in disklist:
        scp(disk, host, backpath_dom)
        print "BACKING UP!!!"
        print disk +' '+ host +' '+ backpath_dom
        
    sleep(2)
    #Only resume if the dom was running
    if before_status == 'running':
        invoke(dom, 'resume')
        
        
def is_disk_mounted ( DISK_UUID, backpath ):
    '''IN case the disk is not ready we exit the script'''
    if not os.path.ismount(backpath):
      status_code = subprocess.Popen(["mount", "-U", DISK_UUID, backpath]).wait()
      if status_code != 0:
	logit( "libvirt error", "Failed, DISK NOT MOUNTED AND NOT POSSIBLE TO MOUNT" )
	sys.exit(2)
    

if __name__ == '__main__':  
    
    SASL_USER = "user"
    SASL_PASS = "password"
    SPEED_NET = 25 #MB. Just to take time statistics
    backpath='/media/VPS_BACKUPs'
    
    # Used to check if the disk exist
    DISK_UUID="" # for example, blkid /dev/sda1
    
    #Fisrt thing we do is to check if the disk is ready:
    is_disk_mounted ( DISK_UUID, backpath )
    
    #Setup how many days before the backup the system will send a reminder by email
    #The thurday before we send a recordatory email. 3 days before
    REMINDER_DAYS_BACKUP = 3
    
    doms_to_backup = [
    # You can have tuples in this format:
    # [Name, Host, Order, services]
        ["database.example.com", "10.2.4.69", 1, "Mysql"],
        ["web.example.com", "10.2.4.69", 1, "project1, project2"],
        ["net.example.com", "10.2.4.69", 0, "DNS, DHCP"],
    ]
    
   
    current_connections={}
    #We backup on Sundays
    if is_last_sun_of_month():
        
        for dom_to_backup in sorted(doms_to_backup, key=lambda dom: dom[2]):
            host=dom_to_backup[1]
            print "Connecting to: " + host
            print "Backing up: " + dom_to_backup[0]
            
            if not current_connections.has_key(host):
                print "We create connecton to: " + host
                host_conn=Domfetcher(SASL_USER, SASL_PASS, 'qemu+tcp://'+host+'/system')
                current_connections.setdefault(host, host_conn)
                
            host_conn=current_connections.get(host)
            dom=host_conn.get_backup_dom(dom_to_backup)
            
            
            #We execute the action we want per each dom
            if dom != None:
                dom_size = host_conn.get_disk_size(dom)
                print "Size to backup: " + str(dom_size) + " MB"
                stimation_time = dom_size / SPEED_NET / 60
                print "Estiamtion time: " + str(stimation_time) + " minutes"
                #backup(dom, backpath, host)
    else:
        days_to_backup=get_day_backup().day-dt.date.today().day
        from datetime import timedelta
        if days_to_backup == REMINDER_DAYS_BACKUP:
            txt="This is auto email from BACKUP SYSTEM. This sunday all servers will be buckup.\
            Please find below more into and time estimation time: \n"
            now_hour=dt.datetime.now()
            count_hours=now_hour
            for dom_to_backup in sorted(doms_to_backup, key=lambda dom: dom[2]):
                host=dom_to_backup[1]
                if not current_connections.has_key(host):
                    print "We create connecton to: " + host
                    host_conn=Domfetcher(SASL_USER, SASL_PASS, 'qemu+tcp://'+host+'/system')
                    current_connections.setdefault(host, host_conn)
                    
                host_conn=current_connections.get(host)
                dom=host_conn.get_backup_dom(dom_to_backup)
                
                if dom != None:
                    dom_time = host_conn.get_disk_size(dom) / SPEED_NET / 60 #in minutes
                    count_hours=count_hours+timedelta(minutes=dom_time) + timedelta(minutes = 5) #We add 5 extra minutes
                    #dom_time + 0.05 #5 extra minutes 
                    txt+="\n"
                    txt+="Server: " + dom_to_backup[0] + "\n"\
                    "Estimation time for the down time: FROM " + now_hour.strftime("%H:%M") +' TO '+ count_hours.strftime("%H:%M") + " hours." + "\n"\
                    "Services will be affected: "+ dom_to_backup[3] 
                    txt+="\n"
                    now_hour=count_hours
                    
            subject="PERFORME VPS BACKUPS"
            txt+="\n\n BACKUP CALENDAR FOR " +str(dt.datetime.today().year)+ ":\n"
            txt+="\n".join( str(x) for x in get_calendar_backup())
            
            mail(txt, subject, NOTIFY_BACKUP_EMAIL_LIST)
    