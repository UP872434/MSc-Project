import requests
from dotenv import load_dotenv
import os
from tinydb import TinyDB, Query
from flask import Flask, request, render_template, redirect
from geopy.geocoders import Nominatim
import folium
import json

app = Flask(__name__)

load_dotenv()

db = TinyDB('db.json')
user = Query()
current_user = None

API_KEY = os.getenv('API_KEY')

@app.route("/", methods = ["GET", "POST"])
@app.route("/login", methods = ["GET", "POST"])
def message():
    global current_user
    error_message = None
    if current_user is not None:
        return render_template('search.html', logged_in=True)
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        u_obj = db.search(user.name == username)

        if len(u_obj) > 0 and u_obj[0]['password'] == password:
            current_user = username
            return render_template('search.html', logged_in=True)
        else:
            error_message = 'Username or password is incorrect'

    return render_template('index.html', logged_in=False, error_message=error_message)

@app.route("/search", methods=["GET", "POST"])
def get_number_details():
    if current_user is not None:
        return render_template('search.html', logged_in=True)
    return redirect('/login')

@app.route("/history", methods=["GET", "POST"])
def history():
    if request.method == "POST":
        number = request.form['number']
        user_obj = db.search(user.name == current_user)[0]
        if 'history' in user_obj and user_obj['history'] is not None:
            values = []
            histories = user_obj['history'].values()
            for history in histories:
                if history['number'].startswith(number):
                    values.append(history)
            chart_keys, chart_values = get_chart_data(histories=values)
            return render_template('history.html', histories=values, display=True, logged_in=True, chart_keys=chart_keys, chart_values=chart_values)
        else:
            histories = None
            return render_template('history.html', histories=histories, display=False, logged_in=True, chart_keys=None, chart_values=None)

    user_obj = db.search(user.name == current_user)[0]
    if 'history' in user_obj and user_obj['history'] is not None:
        histories = user_obj['history'].values()
        chart_keys, chart_values = get_chart_data(histories=histories)
        return render_template('history.html', histories=histories, display=True, logged_in=True, chart_keys=chart_keys, chart_values=chart_values)
    else:
        histories = None
        return render_template('history.html', histories=histories, display=False, logged_in=True, chart_keys=None, chart_values=None)

def get_chart_data(histories):
    chart_data = {}
    for history in histories:
        sp = history['carrier']
        if sp is None or len(sp) == 0:
            if 'Unknown' in chart_data:
                u_num_count = chart_data['Unknown']
                chart_data['Unknown'] = u_num_count + 1
            else:
                chart_data['Unknown'] = 1
        else:
            sp = str(sp.split(" ")[0])
            sp = sp.strip()
            if sp in chart_data:
                num_count = chart_data[sp]
                chart_data[sp] = num_count + 1
            else:
                chart_data[sp] = 1
    return json.dumps(list(chart_data.keys())), json.dumps(list(chart_data.values()))

@app.route("/logout", methods=["GET", "POST"])
def logout():
    global current_user
    current_user = None
    return redirect('/login')

@app.route("/details", methods=["POST"])
def show_number_details():
    if request.method == "POST":
        number = request.form['phonenumber']
        try:
            url = f"https://apilayer.net/api/validate?access_key={API_KEY}&number={number}"
            res = requests.get(url).json()
            
            print(f'Response is {res}')

            if "valid" in res and res["valid"]:
                country_name = get_country_name(res['country_name'])

                location = res['location']
                if location is None or len(location) == 0:
                    location = country_name

                geolocator = Nominatim(user_agent="phone_tracker")
                loc = geolocator.geocode(location)

                map = folium.Map(location=[loc.latitude, loc.longitude], zoom_start=10)
                folium.Marker(
                    [loc.latitude, loc.longitude], popup="<i>Approx location</i>", tooltip="Details"
                ).add_to(map)
                map.save('static/map.html')

                num = res['number']
                detail = {
                    'country': country_name,
                    'carrier': res['carrier'],
                    'location': res['location'],
                    'valid': res['valid'],
                    'message': None,
                    'number': num,
                    'latitude': loc.latitude,
                    'longitude': loc.longitude
                }
                user_obj = db.search(user.name == current_user)[0]
                
                if 'history' in user_obj and user_obj['history'] is not None:
                    history = user_obj['history']
                    if num not in history:
                        history[num] = detail
                else:
                    history = {}
                    history[num] = detail
                user_obj['history'] = history
                db.update(user_obj)

                return render_template('details.html', detail=detail, logged_in=True)
            else:
                return render_template('search.html', error_message="Not a valid number", logged_in=True)
        except Exception as e:
            print(e)
            return render_template('search.html', error_message="Error occured while fetching number details", logged_in=True)

def get_country_name(country_name):
    if '(' in country_name:
        country_name = country_name.split('(')[0]
    return country_name

if __name__ == "__main__":
    app.run(port=9999)