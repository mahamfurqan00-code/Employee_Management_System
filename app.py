from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, func
from datetime import date, datetime
from pathlib import Path
import tempfile
import os, csv, io

app=Flask(__name__)
def _database_uri():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        if database_url.startswith("postgres://"):
            return database_url.replace("postgres://", "postgresql+psycopg://", 1)
        if database_url.startswith("postgresql://"):
            return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return database_url
    if os.environ.get("VERCEL"):
        database_path = (Path(tempfile.gettempdir()) / "peopleops.db").as_posix()
        return f"sqlite:///{database_path}"
    return "sqlite:///peopleops.db"

app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "change-me"),
    SQLALCHEMY_DATABASE_URI=_database_uri(),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)
db=SQLAlchemy(app)

class Employee(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    employee_code=db.Column(db.String(20),unique=True,nullable=False)
    first_name=db.Column(db.String(80),nullable=False)
    last_name=db.Column(db.String(80),nullable=False)
    email=db.Column(db.String(120),unique=True,nullable=False)
    phone=db.Column(db.String(30))
    department=db.Column(db.String(80),nullable=False)
    job_title=db.Column(db.String(100),nullable=False)
    employment_type=db.Column(db.String(30),default="Full-time")
    status=db.Column(db.String(20),default="Active")
    salary=db.Column(db.Float,default=0)
    hire_date=db.Column(db.Date,default=date.today)
    @property
    def full_name(self): return self.first_name+" "+self.last_name

with app.app_context():
    db.create_all()
    if Employee.query.count()==0:
        samples=[
        ("EMP-1001","Ayesha","Khan","ayesha@example.com","Engineering","Python Developer",145000,"2023-04-10"),
        ("EMP-1002","Hamza","Ali","hamza@example.com","Human Resources","HR Executive",95000,"2022-11-21"),
        ("EMP-1003","Sara","Ahmed","sara@example.com","Finance","Accountant",110000,"2024-01-15"),
        ("EMP-1004","Bilal","Sheikh","bilal@example.com","Marketing","Marketing Specialist",105000,"2021-08-02"),
        ("EMP-1005","Mariam","Iqbal","mariam@example.com","Engineering","QA Engineer",125000,"2023-09-18")]
        for code,fn,ln,email,dept,title,salary,hd in samples:
            db.session.add(Employee(employee_code=code,first_name=fn,last_name=ln,email=email,department=dept,job_title=title,salary=salary,hire_date=datetime.strptime(hd,"%Y-%m-%d").date()))
        db.session.commit()

@app.route("/")
def dashboard():
    total=Employee.query.count()
    active=Employee.query.filter_by(status="Active").count()
    depts=db.session.query(func.count(func.distinct(Employee.department))).scalar() or 0
    avg=db.session.query(func.avg(Employee.salary)).scalar() or 0
    latest=Employee.query.order_by(Employee.hire_date.desc()).limit(5).all()
    dist=db.session.query(Employee.department,func.count(Employee.id)).group_by(Employee.department).all()
    return render_template("dashboard.html",total=total,active=active,depts=depts,avg=avg,latest=latest,dist=dist)

@app.route("/employees")
def employees():
    q=request.args.get("q","").strip(); dept=request.args.get("department",""); status=request.args.get("status","")
    query=Employee.query
    if q:
        like=f"%{q}%"
        query=query.filter(or_(Employee.first_name.ilike(like),Employee.last_name.ilike(like),Employee.email.ilike(like),Employee.employee_code.ilike(like),Employee.job_title.ilike(like)))
    if dept: query=query.filter_by(department=dept)
    if status: query=query.filter_by(status=status)
    depts=[x[0] for x in db.session.query(Employee.department).distinct().all()]
    return render_template("employees.html",employees=query.order_by(Employee.id.desc()).all(),q=q,dept=dept,status=status,depts=depts)

def formdata():
    return {k:request.form.get(k,"").strip() for k in ["employee_code","first_name","last_name","email","phone","department","job_title","employment_type","status","salary","hire_date"]}

@app.route("/employees/new",methods=["GET","POST"])
def add_employee():
    if request.method=="POST":
        d=formdata()
        try:
            e=Employee(employee_code=d["employee_code"],first_name=d["first_name"],last_name=d["last_name"],email=d["email"],phone=d["phone"],department=d["department"],job_title=d["job_title"],employment_type=d["employment_type"],status=d["status"],salary=float(d["salary"] or 0),hire_date=datetime.strptime(d["hire_date"],"%Y-%m-%d").date())
            db.session.add(e); db.session.commit(); flash("Employee added successfully.","success"); return redirect(url_for("employees"))
        except Exception:
            db.session.rollback(); flash("Unable to save. Check required fields and unique ID/email.","error")
    return render_template("employee_form.html",e=None,today=date.today().isoformat())

@app.route("/employees/<int:eid>/edit",methods=["GET","POST"])
def edit_employee(eid):
    e=Employee.query.get_or_404(eid)
    if request.method=="POST":
        d=formdata()
        try:
            for k in ["employee_code","first_name","last_name","email","phone","department","job_title","employment_type","status"]: setattr(e,k,d[k])
            e.salary=float(d["salary"] or 0); e.hire_date=datetime.strptime(d["hire_date"],"%Y-%m-%d").date()
            db.session.commit(); flash("Employee updated.","success"); return redirect(url_for("employees"))
        except Exception: db.session.rollback(); flash("Unable to update. Check fields.","error")
    return render_template("employee_form.html",e=e,today=date.today().isoformat())

@app.post("/employees/<int:eid>/delete")
def delete_employee(eid):
    db.session.delete(Employee.query.get_or_404(eid)); db.session.commit(); flash("Employee deleted.","success"); return redirect(url_for("employees"))

@app.get("/export")
def export_csv():
    out=io.StringIO(); w=csv.writer(out); w.writerow(["Code","First name","Last name","Email","Department","Job title","Status","Salary","Hire date"])
    for e in Employee.query.all(): w.writerow([e.employee_code,e.first_name,e.last_name,e.email,e.department,e.job_title,e.status,e.salary,e.hire_date])
    return Response("\ufeff"+out.getvalue(),mimetype="text/csv",headers={"Content-Disposition":"attachment; filename=employees.csv"})

@app.get("/api/employees")
def api_employees():
    return jsonify([{"id":e.id,"code":e.employee_code,"name":e.full_name,"email":e.email,"department":e.department,"title":e.job_title,"status":e.status,"salary":e.salary} for e in Employee.query.all()])

@app.get("/health")
def health(): return jsonify(status="ok",app="PeopleOps")

if __name__=="__main__": app.run(debug=True)
