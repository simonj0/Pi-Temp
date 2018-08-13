'''
FILE NAME
pitemp-server.py
Version 9

1. WHAT IT DOES
This version adds support for Plotly.
 
2. REQUIRES
* Any Raspberry Pi

3. ORIGINAL WORK
Raspberry Full Stack 2015, Peter Dalmaris

4. HARDWARE
* Any Raspberry Pi
* DHT11 or 22
* 10KOhm resistor
* Breadboard
* Wires

5. SOFTWARE
Command line terminal
Simple text editor
Libraries:
from flask import Flask, request, render_template, sqlite3

6. WARNING!
None

7. CREATED 

8. TYPICAL OUTPUT
A simple web page served by this flask application in the user's browser.
The page contains the current temperature and humidity.
A second page that displays historical environment data from the SQLite3 database.
The historical records can be selected by specifying a date range in the request URL.
The user can now click on one of the date/time buttons to quickly select one of the available record ranges.
The user can use Jquery widgets to select a date/time range.
The user can explore historical data to Plotly for visualisation and processing.

 // 9. COMMENTS
--
 // 10. END
'''

from flask import Flask, request, redirect, url_for, render_template, jsonify
import time
import datetime
import arrow

app = Flask(__name__)
app.debug = True # Make this False if you are no longer debugging

lastCacheTime = 0
cachedTemperature = 0
cachedHumidity = 0

@app.route("/")
def root():
    return redirect(url_for('temp_current'))

@app.route("/temp_current")
def temp_current():
	humidity, temperature = get_values()
	if humidity is not None and temperature is not None:
		return render_template("temp_current.html",temp=temperature,hum=humidity)
	else:
		return render_template("no_sensor.html")

@app.route("/temp_history", methods=['GET'])  #Add date limits in the URL #Arguments: from=2015-03-04&to=2015-03-05
def temp_history():
	values, timezone, from_date_str, to_date_str = get_records()

	# Create new record tables so that datetimes are adjusted back to the user browser's time zone.
	time_adjusted_values = []
	for record in values:
		local_timedate = arrow.get(record[0], "YYYY-MM-DD HH:mm").to(timezone)
		time_adjusted_values.append([local_timedate.format('YYYY-MM-DD HH:mm'), round(record[2],1), round(record[3],1)])

	print("rendering temp_history.html with: %s, %s, %s" % (timezone, from_date_str, to_date_str))

	return render_template("temp_history.html",
		timezone = timezone,
		values = time_adjusted_values,
		from_date = from_date_str, 
		to_date = to_date_str,
		values_count = len(values),
		query_string = request.query_string)

@app.route("/temp_api")
def temp_api():
	humidity, temperature = get_values()
	return jsonify({'humidity': humidity, 'temperature': temperature})

def get_values():
	global lastCacheTime, cachedHumidity, cachedTemperature
	currentTime = time.time()*1000
	if lastCacheTime + 5000 < currentTime:
		lastCacheTime = currentTime
		import Adafruit_DHT
		cachedHumidity, cachedTemperature = Adafruit_DHT.read_retry(Adafruit_DHT.AM2302, 17)
	return [cachedHumidity, cachedTemperature]

def get_records():
	import sqlite3
	from_date_str = request.args.get('from',time.strftime("%Y-%m-%d 00:00")) #Get the from date value from the URL
	to_date_str   = request.args.get('to',time.strftime("%Y-%m-%d %H:%M"))   #Get the to date value from the URL
	timezone      = request.args.get('timezone','Etc/UTC');
	range_h_form  = request.args.get('range_h','');  #This will return a string, if field range_h exists in the request
	range_h_int   = "NaN"  #initialise this variable with not a number

	print("REQUEST:")
	print(request.args)
	
	try: 
		range_h_int = int(range_h_form)
	except:
		print("range_h_form not a number")


	print("Received from browser: %s, %s, %s, %s" % (from_date_str, to_date_str, timezone, range_h_int))
	
	if not validate_date(from_date_str):			# Validate date before sending it to the DB
		from_date_str = time.strftime("%Y-%m-%d 00:00")
	if not validate_date(to_date_str):
		to_date_str   = time.strftime("%Y-%m-%d %H:%M")		# Validate date before sending it to the DB
	print('2. From: %s, to: %s, timezone: %s' % (from_date_str,to_date_str,timezone))
	# Create datetime object so that we can convert to UTC from the browser's local time
	from_date_obj = datetime.datetime.strptime(from_date_str,'%Y-%m-%d %H:%M')
	to_date_obj   = datetime.datetime.strptime(to_date_str,'%Y-%m-%d %H:%M')

	# If range_h is defined, we don't need the from and to times
	if isinstance(range_h_int,int):	
		arrow_time_from = arrow.utcnow().replace(hours=-range_h_int)
		arrow_time_to   = arrow.utcnow()
		from_date_utc   = arrow_time_from.strftime("%Y-%m-%d %H:%M")	
		to_date_utc     = arrow_time_to.strftime("%Y-%m-%d %H:%M")
		from_date_str   = arrow_time_from.to(timezone).strftime("%Y-%m-%d %H:%M")
		to_date_str     = arrow_time_to.to(timezone).strftime("%Y-%m-%d %H:%M")
	else:
		#Convert datetimes to UTC so we can retrieve the appropriate records from the database
		from_date_utc   = arrow.get(from_date_obj, timezone).to('Etc/UTC').strftime("%Y-%m-%d %H:%M")	
		to_date_utc     = arrow.get(to_date_obj, timezone).to('Etc/UTC').strftime("%Y-%m-%d %H:%M")

	try:
		conn = sqlite3.connect('./pi-temp.db')
		curs = conn.cursor()
		curs.execute("SELECT * FROM sensor_values WHERE rDateTime BETWEEN ? AND ?", (from_date_utc.format('YYYY-MM-DD HH:mm'), to_date_utc.format('YYYY-MM-DD HH:mm')))
		values = curs.fetchall()
	except:
		values = []
	conn.close()

	return [values, timezone, from_date_str, to_date_str]

@app.route("/to_plotly", methods=['GET'])  #This method will send the data to ploty.
def to_plotly():
	import plotly.plotly as py
	import plotly.graph_objs as go

	temperatures, humidities, timezone, from_date_str, to_date_str = get_records()

	# Create new record tables so that datetimes are adjusted back to the user browser's time zone.
	time_series_adjusted_tempreratures = []
	time_series_adjusted_humidities = []
	time_series_temprerature_values = []
	time_series_humidity_values = []

	for record in temperatures:
		local_timedate = go.arrow.get(record[0], "YYYY-MM-DD HH:mm").to(timezone)
		time_series_adjusted_tempreratures.append(local_timedate.format('YYYY-MM-DD HH:mm'))
		time_series_temprerature_values.append(round(record[2],2))

	for record in humidities:
		local_timedate = arrow.get(record[0], "YYYY-MM-DD HH:mm").to(timezone)
		time_series_adjusted_humidities.append(local_timedate.format('YYYY-MM-DD HH:mm'))
		time_series_humidity_values.append(round(record[2],2))

	temp = go.Scatter(
		x=time_series_adjusted_tempreratures,
		y=time_series_temprerature_values,
		name='Temperature'
    	)
	hum = go.Scatter(
		x=time_series_adjusted_humidities,
		y=time_series_humidity_values,
		name='Humidity',
		yaxis='y2'
    	)

	data = go.Data([temp, hum])

	layout = go.Layout(
		title="Temperature and Humidity",
		xaxis=XAxis(
			type='date',
			autorange=True
		),
		yaxis=YAxis(
			title='Celsius',
			type='linear',
			autorange=True
		),
		yaxis2=YAxis(
			title='Percent',
			type='linear',
			autorange=True,
			overlaying='y',
			side='right'
		)
	)
	fig = Figure(data=data, layout=layout)
	plot_url = py.plot(fig, filename='lab_temp_hum')

	return plot_url

def validate_date(d):
    try:
        datetime.datetime.strptime(d, '%Y-%m-%d %H:%M')
        return True
    except ValueError:
        return False

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
