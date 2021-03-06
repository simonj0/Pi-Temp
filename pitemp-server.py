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

class ReverseProxied(object):
    '''Wrap the application in this middleware and configure the 
    front-end server to add these headers, to let you quietly bind 
    this to a URL other than / and to an HTTP scheme that is 
    different than what is used locally.

    In nginx:
    location /myprefix {
        proxy_pass http://192.168.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /myprefix;
        }

    :param app: the WSGI application
    '''
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)


app = Flask(__name__)
app.wsgi_app = ReverseProxied(app.wsgi_app)
app.debug = False # Make this False if you are no longer debugging

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
	values, from_date_str, to_date_str = get_records()

	# Create new record tables so that datetimes are adjusted back to the user browser's time zone.
	adjusted_values = []
	for record in values:
		adjusted_values.append([record[0], round(record[2],1), round(record[3],1)])

	print("rendering temp_history.html with: %s, %s" % (from_date_str, to_date_str))

	return render_template("temp_history.html",
		values = adjusted_values,
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
	from_date_str = request.args.get('from') #Get the from date value from the URL
	to_date_str   = request.args.get('to')   #Get the to date value from the URL
	range_h_form  = request.args.get('range_h','');  #This will return a string, if field range_h exists in the request
	range_h_int   = "NaN"  #initialise this variable with not a number
	
	try: 
		range_h_int = int(range_h_form)
	except:
		print("range_h_form not a number")


	print("Received from browser: %s, %s, %s" % (from_date_str, to_date_str, range_h_int))
	
	if not validate_date(from_date_str):			# Validate date before sending it to the DB
		from_date_str = arrow.now().strftime("%Y-%m-%d 00:00")
	if not validate_date(to_date_str):
		to_date_str   = arrow.now().shift(minutes=+1).strftime("%Y-%m-%d %H:%M")		# Validate date before sending it to the DB
	print('2. From: %s, to: %s' % (from_date_str,to_date_str))

	# If range_h is defined, we don't need the from and to times
	if isinstance(range_h_int,int):	
		arrow_time_from = arrow.now().shift(hours=-range_h_int)
		arrow_time_to   = arrow.now()
		from_date_str   = arrow_time_from.strftime("%Y-%m-%d %H:%M")
		to_date_str     = arrow_time_to.strftime("%Y-%m-%d %H:%M")

	try:
		conn = sqlite3.connect('./pi-temp.db')
		curs = conn.cursor()
		curs.execute("SELECT * FROM sensor_values WHERE rDateTime BETWEEN ? AND ?", (from_date_str.format('YYYY-MM-DD HH:mm'), to_date_str.format('YYYY-MM-DD HH:mm')))
		values = curs.fetchall()
	except:
		values = []
	conn.close()

	return [values, from_date_str, to_date_str]

'''@app.route("/to_plotly", methods=['GET'])  #This method will send the data to ploty.
def to_plotly():
	import plotly.plotly as py
	import plotly.graph_objs as go

	temperatures, humidities, from_date_str, to_date_str = get_records()

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

	return plot_url'''

def validate_date(d):
    try:
        datetime.datetime.strptime(d, '%Y-%m-%d %H:%M')
        return True
    except:
        return False

if __name__ == "__main__":
    #app.run(host='0.0.0.0', port=8080)
    app.run(port=8080)
