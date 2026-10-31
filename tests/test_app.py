from app import app
def test_health():
    app.config['TESTING']=True
    response=app.test_client().get('/health')
    assert response.status_code==200
    assert response.get_json()['status']=='ok'
def test_dashboard():
    app.config['TESTING']=True
    assert app.test_client().get('/').status_code==200
