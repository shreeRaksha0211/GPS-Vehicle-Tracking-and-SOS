# SafeTrack — consent-based vehicle tracker

Includes Flask web dashboard, SQLite storage, Leaflet live map, owner-authorized viewer access, SOS alerts by optional Twilio SMS, and Android GPS client.

## Run the web server on Windows
1. Install Python 3.11+ and extract this ZIP.
2. Open the folder in VS Code; open Terminal:
   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   copy .env.example .env
   ```
3. Edit `.env`, set `FLASK_SECRET` to a long random value. SMS settings are optional.
4. Run `python app.py`, then open `http://127.0.0.1:5000`.

Create an account, register a vehicle, and copy its one-time device secret. Add emergency contacts with country code such as +91.

## Android
Open `android/` in Android Studio, sync Gradle and run on a real phone. Edit `Config.BASE_URL`: emulator uses `http://10.0.2.2:5000/`; real phone on same Wi-Fi uses your computer's LAN IP; deployed server must use HTTPS. Register vehicle in web dashboard, then enter its ID and device secret in Android app. Grant permissions and start visible GPS tracking. A persistent notification remains visible; tap Stop in app to end.

## GPS hardware
A compatible tracker or gateway must POST JSON to `/api/location`:
```json
{"vehicle_id":1,"device_secret":"ONE_TIME_SECRET","lat":12.9716,"lon":77.5946,"accuracy":8,"speed":5,"heading":90}
```
Hardware protocols vary; a vendor gateway may be needed. Keep device secret private.

## API
`POST /api/register`, `/api/login`, `/api/logout`; `POST /api/vehicles`; `GET /api/vehicles`; `POST /api/location`; `GET /api/vehicles/<id>/location`; `POST /api/vehicles/<id>/share`; `DELETE /api/vehicles/<id>/share/<viewer_id>`; `POST /api/contacts`; `POST /api/vehicles/<id>/sos`.

## SMS
Configure Twilio credentials in `.env` to send SMS. For India, sender IDs, DLT/template and route rules may apply. Check current provider requirements. SMS is not guaranteed; the app saves SOS event and reports provider result. Never rely on this app alone in an emergency; contact local emergency services.

## Critical limitations and production checklist
- A number plate alone cannot provide a live GPS position. The number identifies only a vehicle registered in this app; GPS comes from the owner's phone or an installed GPS tracker.
- This app cannot locate arbitrary vehicles or access police/VAHAN/private vehicle databases.
- The sample is a development MVP, not production-hardened. Before public launch add HTTPS, CSRF protection, rate limits, secure cookie flags, audit logging, consent/retention/deletion controls, backup, database migrations, monitoring, secret rotation, SMS abuse controls, and security review.
- Android permissions and foreground service/background location policies vary by Android version. Test actual target devices and complete required OS permission flows before distribution.
- Do not hide tracking. Share location only with informed consent and revoke access when no longer needed.
