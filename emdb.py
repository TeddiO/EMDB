#!/usr/bin/python3

import os, sys, subprocess, datetime, time, shlex, sqlite3, json, gzip, shutil

'''
Potentially there are two ways to manage backup scripts. One is a cronjob per timeframe (hourly / weekly / monthly etc) or instead, we can have a single file do the legwork.
With that in mind we employ the sqlite3 db just to track our cooldowns for us. This means we can run the script daily (or in whatever timeframe that's required) and as long
as we've got specified cooldowns, the script can actually take care of the rest.
'''

# A quick way to let us generate the string required for when we execute mysqldump. 
baseExecuteString = "-u {0} -p{1} {2} {3} --result-file={4}"
def GenerateExecuteString(dictNamespace, strDumpExecutable, strGlobalRemoteHost = None):
	# Just in case someone using the default config leaves a blank string...
	if strGlobalRemoteHost == "":
		strGlobalRemoteHost = None

	if strGlobalRemoteHost is None and "remoteHost" in dictNamespace:
		# This allows us to have namespaced remotes if we need them.
		strGlobalRemoteHost = dictNamespace["remoteHost"]

	if strGlobalRemoteHost is not None:
		return "{0} -h {1} {2}".format(strDumpExecutable, strGlobalRemoteHost, baseExecuteString)

	return  "{0} {1}".format(strDumpExecutable, baseExecuteString)

def CompressFiles(filePath):

	try:
		with open(filePath, 'rb') as fInput:
			with gzip.open(filePath + ".gz", "wb") as fOutput:
				shutil.copyfileobj(fInput, fOutput)
	except Exception as Error:
		print(Error)
	else:
		os.remove(filePath)

if __name__ == "__main__":
	
	targetConfig = None
	config = None
	if len(sys.argv) > 2 and os.path.isfile(sys.argv[1]):
		targetconfig = sys.argv[1]
	else:
		targetConfig = "config.json"

	try:
		with open(targetConfig) as f:
			config = json.loads(f.read())
	except FileNotFoundError as Error:
		print(Error)
		sys.exit(1)

	if 'dbCooldownTracker' in config and config.get("dbCooldownTracker", "") != "":
		conn = sqlite3.connect(config["dbCooldownTracker"])
	else:
		conn = sqlite3.connect('backuptracker.db')
	cursor = conn.cursor()

	# Just in case we're having to work with sqlite older than 3.3...
	tableCheck = cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE name ='sqlcooldown' and type='table';")
	if tableCheck.fetchone()[0] == 0:
		cursor.execute('CREATE TABLE sqlcooldown (cdtype CHAR(10) PRIMARY KEY NOT NULL, timestamp INT NOT NULL DEFAULT 0);')
	# Allows you to specify your own backup path if the directory you're running the script in isn't ideal.
	if "backupPath" in config and (config.get("backupPath", "") is not ""):
		backupPath = os.path.normpath(config["backupPath"])
	else:
		backupPath = os.path.normpath("{0}/backups".format(os.getcwd()))

	if not os.path.isdir(backupPath):
		os.makedirs(backupPath)

	for namespace, subtbl in config["databases"].items():

		backupName = "{0}{1}{2}-backup.sql"
		finalBackupDir = os.path.join(backupPath, namespace)

		if not os.path.isdir(finalBackupDir):
			os.makedirs(finalBackupDir)

		curTime = int(time.time())
		checkCooldown = cursor.execute("SELECT (timestamp) FROM sqlcooldown WHERE cdtype=(?)", [namespace])
		cooldown = checkCooldown.fetchone()
		if cooldown is None:
			cursor.execute("INSERT INTO sqlcooldown (timestamp, cdtype) VALUES (?, ?)", ((curTime + subtbl["updateRate"] - 20 ) or 0, namespace))
			conn.commit()
		elif cooldown[0] < curTime:
			cursor.execute("UPDATE sqlcooldown SET timestamp = ? WHERE cdtype = ?", ((curTime + subtbl["updateRate"]- 20) or 0, namespace))
			conn.commit()
		else:
			continue

		# To prevent nuking database performance (assuming single instance of mysql / mariaDB) we'll wait for each instance to complete first.
		for db in subtbl['targetData']:
			# If we have a list, only process tables in said list.

			executeString = GenerateExecuteString(db, config.get("mysqldumpPath", "mysqldump --single-transaction"), config.get("remoteHost"))
			if isinstance(db, list):
				targetDB = db[0]
				fileName = backupName.format(namespace, targetDB, datetime.date.today())
				db.pop(0)
				targetTables = " ".join(db)
				finalPath = os.path.join(finalBackupDir, fileName)
				process = subprocess.Popen(shlex.split(executeString.format(config["user"], config["password"], targetDB, targetTables, finalPath)))
				while process.poll() != 0:
					continue

				if config.get("noCompress", False) or subtbl.get("noCompress", False):
					continue

				CompressFiles(finalPath)
			else:
				#Bog standard backup. 
				fileName = backupName.format(namespace, db,datetime.date.today())
				finalPath = os.path.join(finalBackupDir, fileName)
				process = subprocess.Popen(shlex.split(executeString.format(config["user"], config["password"], db, "", finalPath)))
				while process.poll() != 0:
					continue

				if config.get("noCompress", False) or subtbl.get("noCompress", False):
					continue
				
				CompressFiles(finalPath)

	cursor.close()
	conn.close()

