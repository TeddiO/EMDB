# EMDB (Easy MySQL Database Backup)
A small Python 3 script that allows you to quickly and easily back up MySQL Databases

This small script came about as the result of having to back up multiple databases on one machine. What ended up being essentially duplicates of similar scripts have now been emalgimated into EMDB.

## Setting up EMDB
EMDB is reasonably flexible when it comes to setting up various times for backing up databases. While the wording of "daily", "weekly" and "monthly" are in the default config file; you could literally use any name you wanted.

EMDB relies on the idea of you knowing how long (in seconds) you want each backup to be taken. For example:
```Python
config["databases"]["daily"] = {"updateRate": 86400, "targetData": ["my_database"] }
```
What the above will do is back up the database "my_database" every 24 hours (cron job / alternative permitting!) and dump it in a backups/daily folder. Naturally you can just specify multiple databaes in the list to do numerous, individual backups as such - 
```Python
config["databases"]["daily"] = {"updateRate": 86400, "targetData": ["my_database", "my_database2", "my_databaseN"] }
```
### Specifying Tables
When we do backups, we don't always want to grab the entire database - but instead just aspects of it. Thankfully EMDB gives us a way to do this. By specifying a List with the first argument being the database we're after and the rest bein the tables we can grab what we need. For example: 
```Python
config["databases"]["weekly"] = {"updateRate": 604800, "targetData": ["my_database", "my_database2", ["my_database3", "table1", "table2", "table3"], "my_database4"]}
```
As seen, we can specify an unlimited amount of arguments for tables. 

## Suggested Usage

It's recommended to use cron (*nix) or task scheduler (Windows) with a daily (or hourly if you need that) schedule. The script internally will keep an eye when backups so there's no need to set up various cronjobs that all do exactly the same thing!
