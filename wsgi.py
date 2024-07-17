from main import app,vd_blueprint

if __name__ == "__main__":
    app.register_blueprint(vd_blueprint,url_prefix='/vd')
    app.run()

