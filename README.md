# Notebook Price Observatory

ระบบรวบรวมและเปรียบเทียบราคาโน้ตบุ๊ก Windows ราคา 15,000–40,000 บาท จากร้านค้าออนไลน์ในประเทศไทย สำหรับข้อสอบวิชา 02739452

ผู้จัดทำ: นายธีรพงศ์ กลิ่นฟุ้ง รหัสนิสิต 6621600925 หมู่ 700

ลำดับที่จอง: 12 · [GitHub repository](https://github.com/Theerapong25/02739452-12-6621600925)

## แหล่งข้อมูล

1. [Advice Notebook Price List](https://www.advice.co.th/nescen-n053/product/pricelist?cate=notebooks)
2. [JIB Notebook](https://www.jib.co.th/web/product/product_list/2/25), [Gaming](https://www.jib.co.th/web/product/product_list/2/1338), [Ultrathin](https://www.jib.co.th/web/product/product_list/2/1468)
3. [Mercular Notebook](https://www.mercular.com/computer/laptop)

หน้าเว็บทั้งสามแสดงชื่อสินค้าและราคาแบบสาธารณะ ตัวดึงข้อมูลตรวจ `robots.txt` ก่อนเข้าหน้าเว็บทุกครั้ง ไม่ใช้ Selenium ไม่ดึงข้อมูลส่วนบุคคลหรือรูปภาพ Advice และ Mercular ดึงหน้ารายการแหล่งละหนึ่งหน้า ส่วน JIB ดึงสามหมวดย่อยโดยเว้น 1 วินาทีระหว่างหน้า

> แหล่งที่สามเปลี่ยนเป็น Mercular หลังตรวจว่าหน้า invadeIT ที่เปิดด้วย HTTP ปกติยังไม่มีรายการสินค้าใน HTML ที่ส่งกลับ จึงเลือกหน้า Mercular ที่มีข้อมูลจริงและตรวจสอบได้ หากโพสต์จองหัวข้อระบุ invadeIT ไว้ ให้แก้แหล่งที่สามในโพสต์/แจ้งอาจารย์ตามกติกาการจอง

## เปิดใช้งาน

ต้องมี Docker Desktop เปิดอยู่ ใน PowerShell ที่โฟลเดอร์นี้รัน:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

สคริปต์จะสร้าง `.env` พร้อมรหัสผ่านสุ่ม เปิดระบบ และสั่งรัน DAG หนึ่งครั้ง หากต้องการรันใหม่ เปิด [Airflow](http://localhost:8090) แล้ว trigger `notebook_price_comparison` หรือรัน `start.ps1` อีกครั้ง เปิด [Dashboard](http://localhost:8502) เพื่อดูข้อมูลจาก PostgreSQL โดยตรง รหัสผ่าน Airflow และ PostgreSQL อยู่ใน `.env` ซึ่ง Git ไม่เก็บ

| บริการ | ที่อยู่ |
|---|---|
| Dashboard | http://localhost:8502 |
| Airflow | http://localhost:8090 |
| PostgreSQL | localhost:55437, database `notebooks` |

หยุดระบบด้วย `powershell -ExecutionPolicy Bypass -File .\stop.ps1`

## โครงสร้าง

```text
dags/notebook_price_pipeline.py  DAG และ TaskGroup ดึงข้อมูลสามแหล่ง
scraper.py                       ตรวจ robots.txt และแปลง HTML เป็นรายการสินค้า
pipeline.py                      ทำความสะอาด รวมรหัสรุ่น ตรวจคุณภาพ และ UPSERT
web/                             Dashboard Flask อ่าน PostgreSQL โดยตรง
docker-compose.yml               Airflow, PostgreSQL, Dashboard
start.ps1 / stop.ps1             เปิดและปิดระบบบน Windows
```

DAG: `prepare_run → extract_sources (3 งานขนาน) → transform → quality_gate → load_postgres / quality_failed → notify_status`

หากแหล่งใดดึงไม่สำเร็จ งานอื่นยังทำต่อได้ เกณฑ์คุณภาพคือมีข้อมูลที่ราคาอยู่ในช่วง **อย่างน้อย 100 รายการจากอย่างน้อย 2 แหล่ง** ก่อนบันทึกข้อมูล ตาราง `notebook_products` เก็บรหัสรุ่นไม่ซ้ำข้ามร้าน ส่วน `notebook_offers` เก็บราคาของแต่ละร้านเพื่อให้เปรียบเทียบกันได้ รันซ้ำจะ UPSERT ไม่เพิ่มรายการเดิมซ้ำ และลบข้อเสนอที่หายไปจากหน้าเว็บของแหล่งที่ดึงสำเร็จ ตาราง `notebook_pipeline_runs` แสดงสถานะและจำนวนจากแต่ละแหล่ง

ข้อมูลที่ได้คือ **ราคา ณ เวลาดึงข้อมูล** ไม่ใช่ประวัติราคาย้อนหลัง ชื่อรุ่นที่จับคู่ไม่ได้จะเก็บเป็นรหัสเฉพาะแหล่งเพื่อไม่รวมสินค้าคนละรุ่นผิดพลาด

## ตรวจใน DBeaver

สร้างการเชื่อมต่อ PostgreSQL ด้วย `localhost:55437`, database/user `notebooks`, password จาก `.env` แล้วลอง:

```sql
SELECT COUNT(*) FROM notebook_offers;
SELECT COUNT(*) FROM notebook_products;
SELECT source, COUNT(*) FROM notebook_offers GROUP BY source ORDER BY source;
SELECT source, product_name, price_baht, model_key FROM notebook_offers ORDER BY price_baht LIMIT 20;
SELECT * FROM notebook_pipeline_runs ORDER BY finished_at DESC LIMIT 5;
```

## สิ่งที่ต้องส่งตามข้อสอบ

ส่ง [repo นี้](https://github.com/Theerapong25/02739452-12-6621600925) แบบ public และไฟล์ [12_6621600925_summary.pdf](output/pdf/12_6621600925_summary.pdf) ทาง Classroom ก่อน 16:00 น. ห้ามอัปโหลด `.env`, `data/` หรือ `research/`
