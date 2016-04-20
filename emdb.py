import os, sys, subprocess
import datetime
import time
import shlex
from os import path
from config import config
import sqlite3


'''
Potentially there are two ways to manage backup scripts. One is a cronjob per timeframe (hourly / weekly / monthly etc) or instead, we can have a single file do the legwork.
With that in mind we employ the sqlite3 db just to track our cooldowns for us. This means we can run the script daily (or in whatever timeframe that's required) and as long
as we've got specified cooldowns, the script can actually take care of the rest.
'''
if 'dbCooldownTracker' in config and config['dbCooldownTracker'] != "":
	conn = sqlite3.connect(config["dbCooldownTracker"])
else:
	conn = sqlite3.connect('backuptracker.db')
cursor = conn.cursor()
#this tableCheck query allows us to work with sqlite DB's older than ver 3.3.
tableCheck = cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE name ='sqlcooldown' and type='table';")
if tableCheck.fetchone()[0] == 0:
	cursor.execute('CREATE TABLE sqlcooldown (cdtype CHAR(10) PRIMARY KEY NOT NULL,timestamp INT NOT NULL DEFAULT 0);')

#Allows you to specify your own backup path if the directory you're running the script in isn't ideal.
backupPath = config["backupPath"] if "backupPath" in config and config["backupPath"] is not None else os.getcwd() + "/backups/"

print(backupPath)
#Just ensuring the direcetory does exist. 
if not os.path.isdir(backupPath):
	os.makedirs(backupPath)

#Basic string required for dumping DB's. We use --result-file as opposed to > to ensure consistency (and to prevent issues with UTF-16 should it arise)
if 'mysqldumpPath' in config and config["mysqldumpPath"] != "":
	executeString = config["mysqldumpPath"] + " -u {0} -p{1} {2} {3} --result-file={4}"
else:
	executeString = "mysqldump -u {0} -p{1} {2} {3} --result-file={4}"


for schedule, subtbl in config["databases"].items():

	backupName = "{0}{1}{2}-backup.sql"
	#Checks to ensure our designated backuptypes can be dumped in the appropriate folders. 
	if not os.path.isdir(backupPath + schedule):
		os.makedirs(backupPath + schedule)

	#Perform cooldown checks.
	curTime = int(time.time())
	checkCooldown = conn.execute("SELECT timestamp FROM sqlcooldown WHERE cdtype = ?", (schedule, ))
	cooldown = checkCooldown.fetchone()
	if cooldown is None:
		conn.execute("INSERT INTO sqlcooldown (timestamp, cdtype) VALUES (?, ?)", ((curTime + subtbl["updateRate"]) or 0, schedule ))
		conn.commit()
	elif cooldown[0] < curTime:
		conn.execute("UPDATE sqlcooldown SET timestamp = ? WHERE cdtype = ?", ((curTime + subtbl["updateRate"]) or 0, schedule))
		conn.commit()
	else:
		continue

	#Actual logic where we do the backing up (presuming we don't just continue like above)
	#As we don't want to accidentally back up numerous databases at once, we wait until each backup has finished. 
	for db in subtbl['targetData']:
		#As we may want to back up certain tables within a DB (as opposed to an entire DB) we can pass a list with the db as the first argument, tables for the rest
		#of the arguments and magic will happen!
		if isinstance(db, list):
			targetDB = db[0]
			fileName = backupName.format(schedule,targetDB,datetime.date.today())
			db.pop(0)
			targetTables = " ".join(db)
			print( backupPath + schedule + '/' + fileName)
			process = subprocess.Popen(shlex.split(executeString.format(config["user"], config["password"], targetDB, targetTables,  backupPath + schedule + '/' + fileName)))
			while process.poll() != 0:
				continue
		else:
			#Bog standard backup. 
			fileName = backupName.format(schedule, db,datetime.date.today())
			process = subprocess.Popen(shlex.split(executeString.format(config["user"], config["password"], db, "",  backupPath + schedule + '/' + fileName)))
			while process.poll() != 0:
				continue

#Otherwise, all done!



