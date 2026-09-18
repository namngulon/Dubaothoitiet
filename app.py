from flask import Flask, render_template_string, request, Response
import requests
import csv
import io
import json

app = Flask(__name__)

# Giao diện phong cách AccuWeather (Dark Mode)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AccuWeather Clone - Dự báo & Phân tích</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-color: #121212;
            --card-bg: #1e1e1e;
            --text-main: #ffffff;
            --text-muted: #a0a0a0;
            --accent-orange: #f39c12;
            --accent-blue: #3498db;
            --accent-green: #2ecc71;
            --accent-red: #e74c3c;
        }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: var(--bg-color); color: var(--text-main); margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        
        .header { text-align: center; margin-bottom: 30px; border-bottom: 1px solid #333; padding-bottom: 20px; }
        .header h1 { color: var(--accent-orange); font-size: 32px; margin: 0; letter-spacing: 1px; }
        .header p { color: var(--text-muted); margin-top: 5px; }

        .card { background: var(--card-bg); border-radius: 12px; padding: 25px; box-shadow: 0 8px 16px rgba(0,0,0,0.4); margin-bottom: 25px; border: 1px solid #2a2a2a; }
        
        /* Form nhập liệu */
        .form-row { display: flex; gap: 15px; flex-wrap: wrap; align-items: flex-end; justify-content: center; }
        .input-group { display: flex; flex-direction: column; }
        .input-group label { font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 8px; text-transform: uppercase; }
        .input-group input { padding: 12px; background: #2a2a2a; border: 1px solid #444; color: white; border-radius: 8px; width: 120px; outline: none; }
        .input-group input:focus { border-color: var(--accent-orange); }
        
        .btn { background: var(--accent-orange); color: #fff; border: none; padding: 12px 25px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s; text-decoration: none; }
        .btn:hover { background: #d68910; }
        .btn-csv { background: var(--accent-green); margin-left: 10px; }
        .btn-csv:hover { background: #27ae60; }

        /* Widget Không khí & Dị ứng */
        .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 25px; }
        .status-box { background: #252525; padding: 20px; border-radius: 10px; text-align: center; border-left: 4px solid var(--accent-blue); }
        .status-box.allergy { border-left-color: var(--accent-red); }
        .status-box h3 { margin: 0 0 10px 0; font-size: 16px; color: var(--text-muted); }
        .status-box .value { font-size: 28px; font-weight: bold; }
        .status-box .desc { font-size: 14px; margin-top: 5px; color: #bbb; }

        /* Lưới biểu đồ */
        .charts-grid { display: grid; grid-template-columns: 1fr; gap: 20px; }
        @media (min-width: 900px) { .charts-grid { grid-template-columns: 1fr 1fr; } .chart-full { grid-column: span 2; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌤️ THỜI TIẾT & CHẤT LƯỢNG KHÔNG KHÍ</h1>
            <p>Dữ liệu chuyên sâu - Thiết kế lấy cảm hứng từ AccuWeather</p>
        </div>
        
        <div class="card">
            <form method="POST" class="form-row">
                <div class="input-group">
                    <label>Vĩ độ (Lat)</label>
                    <input type="text" name="lat" value="{{ lat }}" required>
                </div>
                <div class="input-group">
                    <label>Kinh độ (Lon)</label>
                    <input type="text" name="lon" value="{{ lon }}" required>
                </div>
                <div class="input-group">
                    <label>Ngày quá khứ</label>
                    <input type="number" name="past" value="{{ past }}" min="0" max="90">
                </div>
                <div class="input-group">
                    <label>Ngày dự báo</label>
                    <input type="number" name="forecast" value="{{ forecast }}" min="0" max="14">
                </div>
                <div class="input-group" style="flex-direction: row; gap: 10px;">
                    <button type="submit" class="btn">Phân Tích</button>
                    <a href="/download?lat={{lat}}&lon={{lon}}&past={{past}}&forecast={{forecast}}" class="btn btn-csv">📥 Tải .CSV</a>
                </div>
            </form>
        </div>

        {% if weather_json and weather_json != '[]' %}
        
        <!-- Bảng tóm tắt không khí và dị ứng (Lấy dữ liệu tại thời điểm mới nhất) -->
        <div class="status-grid">
            <div class="status-box">
                <h3>Chất lượng không khí (AQI)</h3>
                <div class="value" id="aqi-val">--</div>
                <div class="desc" id="aqi-desc">Bụi mịn PM2.5: <span id="pm25-val">--</span> µg/m³</div>
            </div>
            <div class="status-box allergy">
                <h3>Dự báo Dị ứng (Phấn hoa/Bụi)</h3>
                <div class="value" id="allergy-val">--</div>
                <div class="desc">Chỉ số phát tán dị ứng trong không khí</div>
            </div>
        </div>

        <div class="charts-grid">
            <div class="card chart-full">
                <canvas id="radiationChart" height="80"></canvas>
            </div>
            <div class="card">
                <canvas id="tempChart"></canvas>
            </div>
            <div class="card">
                <canvas id="humidityChart"></canvas>
            </div>
        </div>

        <script>
            // Parse dữ liệu từ Python
            const rawData = {{ weather_json | safe }};
            
            // Lấy dữ liệu mới nhất (phần tử cuối cùng hoặc phần tử hiện tại) để hiển thị lên Widget
            if(rawData.length > 0) {
                // Giả sử lấy mốc giữa dữ liệu làm đại diện hiện tại
                const current = rawData[Math.floor(rawData.length / 2)]; 
                
                document.getElementById('aqi-val').innerText = current.aqi || 0;
                document.getElementById('pm25-val').innerText = current.pm25 || 0;
                
                // Đánh giá AQI
                let aqiDesc = "";
                if(current.aqi < 50) aqiDesc = "Tuyệt vời (Tốt cho sức khỏe)";
                else if(current.aqi < 100) aqiDesc = "Trung bình (Chấp nhận được)";
                else aqiDesc = "Kém (Có hại cho sức khỏe nhạy cảm)";
                document.getElementById('aqi-desc').innerHTML += `<br><span style="color:var(--accent-orange)">${aqiDesc}</span>`;

                // Đánh giá Dị ứng (Phấn hoa)
                let pollen = current.pollen || 0;
                document.getElementById('allergy-val').innerText = pollen + " g/m³";
                if(pollen === 0) document.getElementById('allergy-val').innerText = "Rất thấp";
                else if(pollen < 10) document.getElementById('allergy-val').innerText = "Thấp";
                else document.getElementById('allergy-val').innerText = "Cao (Dễ dị ứng)";
            }

            // Bóc tách mảng cho Chart.js
            const labels = rawData.map(d => d.time);
            const tempData = rawData.map(d => d.temp);
            const humidityData = rawData.map(d => d.humidity);
            const radiationData = rawData.map(d => d.radiation);

            // Cấu hình biểu đồ Dark Mode
            Chart.defaults.color = '#a0a0a0';
            Chart.defaults.font.family = 'Segoe UI';
            
            const commonOptions = {
                responsive: true,
                interaction: { mode: 'index', intersect: false },
                scales: { 
                    x: { grid: { color: '#333' }, ticks: { maxTicksLimit: 15 } },
                    y: { grid: { color: '#333' } }
                }
            };

            // Biểu đồ Bức xạ
            new Chart(document.getElementById('radiationChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: '☀️ Bức xạ mặt trời (W/m²)',
                        data: radiationData,
                        borderColor: '#f39c12', backgroundColor: 'rgba(243, 156, 18, 0.1)',
                        borderWidth: 2, fill: true, tension: 0.4, pointRadius: 0
                    }]
                },
                options: commonOptions
            });

            // Biểu đồ Nhiệt độ
            new Chart(document.getElementById('tempChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: '🌡️ Nhiệt độ (°C)',
                        data: tempData,
                        borderColor: '#e74c3c', backgroundColor: 'rgba(231, 76, 60, 0.1)',
                        borderWidth: 2, fill: true, tension: 0.4, pointRadius: 0
                    }]
                },
                options: commonOptions
            });

            // Biểu đồ Độ ẩm
            new Chart(document.getElementById('humidityChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: '💧 Độ ẩm (%)',
                        data: humidityData,
                        borderColor: '#3498db', backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        borderWidth: 2, fill: true, tension: 0.4, pointRadius: 0
                    }]
                },
                options: commonOptions
            });
        </script>
        {% endif %}
    </div>
</body>
</html>
"""

def fetch_all_data(lat, lon, past, forecast):
    # API 1: Dữ liệu thời tiết (Nhiệt độ, độ ẩm, bức xạ)
    weather_url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                   f"&hourly=temperature_2m,relative_humidity_2m,shortwave_radiation"
                   f"&past_days={past}&forecast_days={forecast}&timezone=Asia%2FBangkok")
    
    # API 2: Dữ liệu Không khí & Dị ứng (AQI, PM2.5, Phấn hoa)
    aqi_url = (f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}"
               f"&hourly=pm10,pm2_5,european_aqi,grass_pollen"
               f"&past_days={past}&forecast_days={forecast}&timezone=Asia%2FBangkok")
    
    try:
        w_res = requests.get(weather_url, timeout=10).json().get("hourly", {})
        a_res = requests.get(aqi_url, timeout=10).json().get("hourly", {})
        
        times = w_res.get("time", [])
        temps = w_res.get("temperature_2m", [])
        humids = w_res.get("relative_humidity_2m", [])
        rads = w_res.get("shortwave_radiation", [])
        
        # Dữ liệu AQI có thể thiếu ở một số khu vực nên cần gán dự phòng
        aqis = a_res.get("european_aqi", [])
        pm25s = a_res.get("pm2_5", [])
        pollens = a_res.get("grass_pollen", [])
        
        results = []
        for i in range(len(times)):
            time_str = times[i].replace("T", " ")
            short_time = time_str[5:16].replace("-", "/")
            
            # Khắc phục lỗi "None" nếu Open-Meteo không có dữ liệu bụi/phấn hoa tại tọa độ đó
            aqi_val = aqis[i] if i < len(aqis) and aqis[i] is not None else 0
            pm25_val = pm25s[i] if i < len(pm25s) and pm25s[i] is not None else 0
            pollen_val = pollens[i] if i < len(pollens) and pollens[i] is not None else 0
            
            results.append({
                "time": short_time,
                "full_time": time_str,
                "temp": temps[i],
                "humidity": humids[i],
                "radiation": rads[i],
                "aqi": aqi_val,
                "pm25": pm25_val,
                "pollen": pollen_val
            })
        return results
    except Exception as e:
        print("Lỗi tải dữ liệu:", e)
    return []

@app.route('/', methods=['GET', 'POST'])
def home():
    lat, lon = "21.0285", "105.8542" # Mặc định Hà Nội
    past, forecast = "2", "3"
    
    if request.method == 'POST':
        lat = request.form.get("lat", lat)
        lon = request.form.get("lon", lon)
        past = request.form.get("past", past)
        forecast = request.form.get("forecast", forecast)
        
    weather_data = fetch_all_data(lat, lon, past, forecast)
    weather_json = json.dumps(weather_data)

    return render_template_string(HTML_TEMPLATE, lat=lat, lon=lon, past=past, forecast=forecast, weather_json=weather_json)

@app.route('/download')
def download_csv():
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    past = request.args.get('past')
    forecast = request.args.get('forecast')
    
    data = fetch_all_data(lat, lon, past, forecast)
    
    si = io.StringIO()
    cw = csv.writer(si)
    # Cập nhật thêm các cột Không khí và Dị ứng vào file CSV
    cw.writerow(['Thoi gian', 'Nhiet do (C)', 'Do am (%)', 'Buc xa mat troi (W/m2)', 'AQI', 'PM 2.5', 'Phan hoa (g/m3)'])
    for row in data:
        cw.writerow([row['full_time'], row['temp'], row['humidity'], row['radiation'], row['aqi'], row['pm25'], row['pollen']])
        
    return Response(
        si.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=AccuWeather_{lat}_{lon}.csv"}
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)