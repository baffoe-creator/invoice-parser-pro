 
urls = [
  "https://invoice-parser-pro-o.onrender.com/",   
  "https://invoice-parser-pro-o.onrender.com/share/zapier",
  "https://invoice-parser-pro-o.onrender.com/share/google-sheets",
]

xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
for u in urls:
    xml += f"<url><loc>{u}</loc></url>"
xml += "</urlset>"

with open("static/sitemap.xml", "w") as f:
    f.write(xml)
print("✅ Sitemap updated with correct URLs")