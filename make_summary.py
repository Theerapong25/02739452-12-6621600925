"""Create a three-page exam summary PDF from the verified local screenshots."""
import argparse
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from PIL import Image

PARSER = argparse.ArgumentParser()
PARSER.add_argument("--order", default="XX", help="Booking sequence number")
PARSER.add_argument("--repo", default="", help="Public GitHub repository URL")
ARGS = PARSER.parse_args()
ROOT = Path(__file__).parent
OUT = ROOT / "output" / "pdf" / f"{ARGS.order}_6621600925_summary.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)
FONT = "C:/Windows/Fonts/tahoma.ttf"
BOLD = "C:/Windows/Fonts/tahomabd.ttf"
pdfmetrics.registerFont(TTFont("Tahoma", FONT))
pdfmetrics.registerFont(TTFont("TahomaBold", BOLD))
W, H = A4
NAVY = colors.HexColor("#102A48")
TEAL = colors.HexColor("#13AFA6")
MUTED = colors.HexColor("#617184")
INK = colors.HexColor("#16283E")


def text(c, x, y, value, size=10, bold=False, color=INK):
    c.setFont("TahomaBold" if bold else "Tahoma", size)
    c.setFillColor(color)
    c.drawString(x, y, value)


def wrapped(c, x, y, value, width=500, size=9, leading=15, bold=False, color=INK):
    words = value.split(" ")
    line = ""
    for word in words:
        candidate = (line + " " + word).strip()
        if pdfmetrics.stringWidth(candidate, "TahomaBold" if bold else "Tahoma", size) > width and line:
            text(c, x, y, line, size, bold, color)
            y -= leading
            line = word
        else:
            line = candidate
    if line:
        text(c, x, y, line, size, bold, color)
        y -= leading
    return y


def header(c, page, section):
    c.setFillColor(NAVY)
    c.rect(0, H - 72, W, 72, fill=1, stroke=0)
    text(c, 40, H - 35, "NOTEBOOK PRICE OBSERVATORY", 17, True, colors.white)
    text(c, 40, H - 54, section, 9, False, colors.HexColor("#75DDD5"))
    c.setStrokeColor(colors.HexColor("#E3E9EF"))
    c.line(40, 45, W - 40, 45)
    text(c, 40, 28, "02739452  |  6621600925  |  หมู่ 700", 8, color=MUTED)
    text(c, W - 80, 28, f"{page} / 3", 8, color=MUTED)


def section(c, y, number, title):
    text(c, 40, y, number, 9, True, TEAL)
    text(c, 65, y, title, 13, True, NAVY)
    return y - 25


def place_image(c, filename, x, top, width, max_height):
    p = ROOT / "report_assets" / filename
    with Image.open(p) as im:
        iw, ih = im.size
    height = min(width * ih / iw, max_height)
    width = height * iw / ih
    c.drawImage(str(p), x, top - height, width, height, preserveAspectRatio=True, mask="auto")
    return top - height


c = canvas.Canvas(str(OUT), pagesize=A4)
c.setTitle("สรุประบบเปรียบเทียบราคาโน้ตบุ๊ก")
c.setAuthor("นายธีรพงศ์ กลิ่นฟุ้ง")

header(c, 1, "ภาพรวมระบบและ Dashboard")
y = H - 96
text(c, 40, y, "นายธีรพงศ์ กลิ่นฟุ้ง  |  รหัสนิสิต 6621600925  |  หมู่ 700", 10, True)
y -= 24
y = wrapped(c, 40, y, "หัวข้อ: เปรียบเทียบราคาโน้ตบุ๊ก Windows ราคา 15,000-40,000 บาท จาก Advice, JIB และ Mercular", 510, 10, 16)
y -= 4
y = wrapped(c, 40, y, "ระบบดึงหน้าเว็บสาธารณะ 3 แหล่ง ผ่าน Airflow TaskGroup แบบขนาน ปรับชื่อรุ่นและราคาให้อยู่ใน schema เดียวกัน แล้ว UPSERT ลง PostgreSQL หน้าเว็บ Flask อ่านฐานข้อมูลโดยตรง", 510, 9, 16)
y -= 8
for line in ["ผลทดสอบจริง 23 ต.ค. 2569: รวม 415 ข้อเสนอ 395 รุ่น จาก 3 ร้าน",
             "Advice 250 รายการ  |  JIB 152 รายการ  |  Mercular 13 รายการ",
             "ระดับที่ทำได้: 1, 2 และ 3  |  โบนัส: หน้าสถานะ Pipeline"]:
    text(c, 40, y, line, 9, True if line.startswith("ผล") else False)
    y -= 16
y -= 5
y = section(c, y, "01", "ภาพหน้าเว็บ Dashboard")
place_image(c, "dashboard-top.png", 40, y, 515, 490)
c.showPage()

header(c, 2, "ผลการรัน Apache Airflow")
y = H - 100
y = section(c, y, "02", "Graph view ของ DAG")
y = place_image(c, "airflow-graph-crop.png", 40, y, 515, 270) - 16
y = section(c, y, "03", "Grid view และผลการรัน")
y = place_image(c, "airflow-grid-crop.png", 40, y, 515, 250) - 12
text(c, 40, y, "รันสำเร็จ 3 ครั้ง  |  งานดึงข้อมูล 3 แหล่งขนานกัน  |  ตรวจคุณภาพก่อนบันทึก", 8.5)
c.showPage()

header(c, 3, "ปัญหา วิธีแก้ และการจัดลำดับงาน")
y = H - 105
y = section(c, y, "04", "ปัญหาที่พบและวิธีแก้")
items = [
    ("1. แหล่งข้อมูลที่สามไม่ส่งรายการใน HTML", [
        "อาการ: หน้า invadeIT ที่ดึงด้วย HTTP ได้โครงหน้า แต่ไม่มีรายการสินค้าให้แปลงข้อมูล",
        "หาสาเหตุ: ตรวจ HTML ที่ตอบกลับ พบว่าสินค้าโหลดภายหลังด้วย JavaScript",
        "วิธีแก้: ใช้ Mercular ซึ่งมีชื่อ ราคา และ URL อยู่ใน HTML จริง และตรวจ robots.txt ก่อนดึง",
    ]),
    ("2. DAG ถูกพักหลังสร้างระบบ", [
        "อาการ: Trigger แล้วสถานะ queued แต่ไม่มี task เริ่มทำงาน",
        "หาสาเหตุ: ตรวจ Airflow พบว่า DAG อยู่ในสถานะ paused",
        "วิธีแก้: เปิด DAG และตั้งค่าให้ DAG ใหม่ไม่ถูกพัก จากนั้นรันสำเร็จ 3 ครั้ง",
    ]),
    ("3. ร้านหลักล่มแล้วข้อมูลอาจไม่ถึงเกณฑ์", [
        "อาการ: สองร้านรองจากการดึงครั้งแรกมีรายการรวมไม่ถึง 100 รายการ",
        "หาสาเหตุ: JIB หน้าเดียวมีรายการในช่วงราคาเพียง 59 รายการ",
        "วิธีแก้: ดึง JIB เพิ่มอีกสองหมวด; ปัจจุบัน JIB กับ Mercular รวม 165 รายการ",
    ]),
]
for title, lines in items:
    text(c, 40, y, title, 10, True)
    y -= 19
    for line in lines:
        y = wrapped(c, 52, y, line, 496, 8.5, 15)
    y -= 11
y = section(c, y, "05", "แผนและลำดับงานภายใน 3 ชั่วโมง")
for line in [
    "13:00-13:25 ตรวจแหล่งข้อมูลและ robots.txt; เลือกหน้าเว็บที่ดึงได้จริง",
    "13:25-14:35 ทำตัวดึงข้อมูล, TaskGroup, schema กลาง, UPSERT และ quality gate",
    "14:35-15:20 ทำ Dashboard ที่อ่าน PostgreSQL โดยตรง พร้อม KPI กราฟ และตัวกรอง",
    "15:20-16:00 ทดสอบรันซ้ำ เก็บภาพ Graph/Grid/Dashboard สรุป PDF และส่ง GitHub",
]:
    y = wrapped(c, 40, y, line, 510, 8.5, 16)
y -= 8
y = wrapped(c, 40, y, "ตัดขอบเขตประวัติราคาย้อนหลังและสเปกละเอียดออก เพื่อให้ครบเงื่อนไขหลักและตรวจการรันจริงทันเวลา", 510, 8.5, 15)
y -= 12
repo_text = ARGS.repo or "รอเลขลำดับจองเพื่อสร้าง repo 02739452-<ลำดับ>-6621600925"
y = wrapped(c, 40, y, "GitHub: " + repo_text, 510, 8.5, 14, True, NAVY)
c.save()
print(OUT)
