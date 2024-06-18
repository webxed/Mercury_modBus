Description:

python3 **mercury_mass_devices_zbx.py** - script for query Mercury devices over COM port and send data to Zabbix https://www.zabbix.com/

python3 **mercury_mass_devices_json.py** - script for query Mercury devices over COM port and save info to json file

**get_data_python3.py** - original script by https://github.com/n0l


----

JQ https://jqlang.github.io/jq/ data dump to CSV examples:

// select data from one device

`cat 2023-09.json | jq ' .[] | select(.SN==131) | (keys_unsorted, [.[]]) | @tsv'`

// select data from two devices and Time 00:00

`cat 2023-09.json | jq ' .[] | select ((.SN==112 or .SN==111) and .Time == "00:00") | "\(.SN);\(.Date);\(.EA)"'`

----
**CRON** task examle

`# */15 * * * * /usr/bin/flock -n /tmp/mercury_mass_devices_zbx.lockfile /usr/bin/python3 /root/Mercury_remote/mercury_mass_devices_zbx.py > /root/Mercury_remote/mercury_mass_devices_zbx.log 2>&1`
