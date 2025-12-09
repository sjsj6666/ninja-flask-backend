@app.route('/debug-proxy')
def debug_proxy():
    try:
        # 1. Check IP WITHOUT Proxy (Direct from Render)
        direct_resp = requests.get("https://api.ipify.org?format=json", timeout=5)
        direct_ip = direct_resp.json().get('ip')

        # 2. Check IP WITH Proxy (Through Alibaba)
        proxy_resp = requests.get("https://api.ipify.org?format=json", proxies=PROXIES, timeout=5)
        proxy_ip = proxy_resp.json().get('ip')

        return jsonify({
            "status": "success",
            "render_server_ip": direct_ip,
            "alibaba_proxy_ip": proxy_ip,
            "proxy_working": direct_ip != proxy_ip and proxy_ip == "47.84.96.104"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
        
