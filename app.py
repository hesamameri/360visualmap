from flask import Flask, render_template, send_from_directory, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy import inspect, text
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class POI(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(50))  # '360' or 'building'
    scene_id = db.Column(db.String(50))  # for 360 POIs

class Poster(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    scene_id = db.Column(db.String(50), nullable=False)
    text = db.Column(db.Text)
    image_url = db.Column(db.String(200))
    color = db.Column(db.String(20))
    pitch = db.Column(db.Float)
    yaw = db.Column(db.Float)
    # Visual scale factor for simulated depth/size in viewer (1.0 = default)
    scale = db.Column(db.Float, default=1.0)
    # Base font size in pixels for poster text (independent of scale)
    font_size = db.Column(db.Float, default=14.0)

class NavLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    scene_id = db.Column(db.String(50), nullable=False)  # source scene
    target_scene_id = db.Column(db.String(50), nullable=False)  # destination scene
    pitch = db.Column(db.Float)
    yaw = db.Column(db.Float)
    label = db.Column(db.String(100))
    color = db.Column(db.String(20))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return redirect(url_for('map_view'))

@app.route('/map')
def map_view():
    pois_query = POI.query.all()
    pois = [{'id': poi.id, 'name': poi.name, 'lat': poi.lat, 'lng': poi.lng, 'type': poi.type, 'scene_id': poi.scene_id} for poi in pois_query]
    return render_template('map.html', pois=pois)

@app.route('/tour/<scene_id>')
def tour(scene_id):
    posters_query = Poster.query.filter_by(scene_id=scene_id).all()
    posters = [{'id': p.id, 'scene_id': p.scene_id, 'text': p.text, 'image_url': p.image_url, 'color': p.color, 'pitch': p.pitch, 'yaw': p.yaw, 'scale': (p.scale if p.scale is not None else 1.0), 'font_size': (p.font_size if p.font_size is not None else 14.0)} for p in posters_query]
    navs_query = NavLink.query.filter_by(scene_id=scene_id).all()
    navs = [{'id': n.id, 'scene_id': n.scene_id, 'target_scene_id': n.target_scene_id, 'pitch': n.pitch, 'yaw': n.yaw, 'label': n.label, 'color': n.color} for n in navs_query]
    # All available 360 scenes for admin to pick targets
    scene_choices = sorted({poi.scene_id for poi in POI.query.filter_by(type='360').all() if poi.scene_id})
    is_admin = current_user.is_authenticated and current_user.is_admin
    return render_template('tour.html', scene_id=scene_id, posters=posters, navs=navs, scenes=scene_choices, is_admin=is_admin)

@app.route('/add_poster', methods=['POST'])
@login_required
def add_poster():
    if not current_user.is_admin:
        return "Not authorized", 403
    scene_id = request.form['scene_id']
    pitch = float(request.form['pitch'])
    yaw = float(request.form['yaw'])
    text = request.form.get('text')
    image_url = request.form.get('image_url')
    color = request.form.get('color', '#fff')
    scale = float(request.form.get('scale', 1.0))
    font_size = float(request.form.get('font_size', 14.0))
    poster = Poster(scene_id=scene_id, pitch=pitch, yaw=yaw, text=text, image_url=image_url, color=color, scale=scale, font_size=font_size)
    db.session.add(poster)
    db.session.commit()
    return redirect(url_for('tour', scene_id=scene_id))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:  # In production, hash passwords
            login_user(user)
            return redirect(url_for('map_view'))
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.is_admin:
        return f"Access denied for {current_user.username}, is_admin: {current_user.is_admin}", 403
    if request.method == 'POST':
        scene_id = request.form['scene_id']
        text = request.form['text']
        image_url = request.form.get('image_url')
        color = request.form['color']
        pitch = float(request.form['pitch'])
        yaw = float(request.form['yaw'])
        poster = Poster(scene_id=scene_id, text=text, image_url=image_url, color=color, pitch=pitch, yaw=yaw)
        db.session.add(poster)
        db.session.commit()
        return redirect(url_for('admin'))
    posters = [{'id': p.id, 'scene_id': p.scene_id, 'text': p.text, 'image_url': p.image_url, 'color': p.color, 'pitch': p.pitch, 'yaw': p.yaw, 'scale': (p.scale if p.scale is not None else 1.0), 'font_size': (p.font_size if p.font_size is not None else 14.0)} for p in Poster.query.all()]
    return render_template('admin.html', posters=posters)

@app.route('/add_nav', methods=['POST'])
@login_required
def add_nav():
    if not current_user.is_admin:
        return "Not authorized", 403
    scene_id = request.form['scene_id']
    target_scene_id = request.form['target_scene_id']
    pitch = float(request.form['pitch'])
    yaw = float(request.form['yaw'])
    label = request.form.get('label')
    color = request.form.get('color', '#22c55e')
    nav = NavLink(scene_id=scene_id, target_scene_id=target_scene_id, pitch=pitch, yaw=yaw, label=label, color=color)
    db.session.add(nav)
    db.session.commit()
    return redirect(url_for('tour', scene_id=scene_id))

@app.route('/delete_nav', methods=['POST'])
@login_required
def delete_nav():
    if not current_user.is_admin:
        return "Not authorized", 403
    nav_id = int(request.form['id'])
    nav = NavLink.query.get_or_404(nav_id)
    scene_id = nav.scene_id
    db.session.delete(nav)
    db.session.commit()
    return redirect(url_for('tour', scene_id=scene_id))

@app.route('/update_nav', methods=['POST'])
@login_required
def update_nav():
    if not current_user.is_admin:
        return "Not authorized", 403
    nav_id = int(request.form['id'])
    nav = NavLink.query.get_or_404(nav_id)
    if 'pitch' in request.form:
        nav.pitch = float(request.form['pitch'])
    if 'yaw' in request.form:
        nav.yaw = float(request.form['yaw'])
    if 'label' in request.form:
        nav.label = request.form['label']
    if 'color' in request.form:
        nav.color = request.form['color']
    db.session.commit()
    return redirect(url_for('tour', scene_id=nav.scene_id))

@app.route('/update_poster', methods=['POST'])
@login_required
def update_poster():
    if not current_user.is_admin:
        return "Not authorized", 403
    poster_id = int(request.form['id'])
    poster = Poster.query.get_or_404(poster_id)
    # Update fields if provided
    if 'pitch' in request.form:
        poster.pitch = float(request.form['pitch'])
    if 'yaw' in request.form:
        poster.yaw = float(request.form['yaw'])
    if 'scale' in request.form:
        poster.scale = float(request.form['scale'])
    if 'font_size' in request.form:
        poster.font_size = float(request.form['font_size'])
    if 'text' in request.form:
        poster.text = request.form['text']
    if 'image_url' in request.form:
        poster.image_url = request.form['image_url']
    if 'color' in request.form:
        poster.color = request.form['color']
    db.session.commit()
    return redirect(url_for('tour', scene_id=poster.scene_id))

@app.route('/delete_poster', methods=['POST'])
@login_required
def delete_poster():
    if not current_user.is_admin:
        return "Not authorized", 403
    poster_id = int(request.form['id'])
    poster = Poster.query.get_or_404(poster_id)
    scene_id = poster.scene_id
    db.session.delete(poster)
    db.session.commit()
    return redirect(url_for('tour', scene_id=scene_id))

@app.route('/sw.js')
def sw():
    return send_from_directory('.', 'sw.js')

@app.route('/<int:image_id>.jpg')
def serve_image(image_id):
    if 1 <= image_id <= 5:
        response = send_from_directory('.', f'{image_id}.jpg')
        # Add cache headers for large images
        response.headers['Cache-Control'] = 'public, max-age=31536000'  # Cache for 1 year
        response.headers['Expires'] = '31536000'  # Expires in 1 year
        return response
    else:
        return "Image not found", 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        cols = [c['name'] for c in inspector.get_columns('poster')]
        if 'scale' not in cols:
            db.session.execute(text("ALTER TABLE poster ADD COLUMN scale FLOAT DEFAULT 1.0"))
            db.session.commit()
        if 'font_size' not in cols:
            db.session.execute(text("ALTER TABLE poster ADD COLUMN font_size FLOAT DEFAULT 14.0"))
            db.session.commit()
        # Add sample data if needed
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password='password', is_admin=True)
            db.session.add(admin)
            db.session.commit()
        admin_user = User.query.filter_by(username='admin').first()
        if admin_user:
            admin_user.is_admin = True
            db.session.commit()
        POI.query.delete()
        pois = [
            POI(name="Entrance 360 View", lat=59.465, lng=9.0372, type="360", scene_id="scene1"),
            POI(name="Gallery 360 View", lat=59.4655, lng=9.0377, type="360", scene_id="scene2"),
            POI(name="Exhibit Hall 360", lat=59.466, lng=9.0382, type="360", scene_id="scene3"),
            POI(name="Outdoor Area 360", lat=59.4665, lng=9.0387, type="360", scene_id="scene4"),
            POI(name="Final View 360", lat=59.467, lng=9.0392, type="360", scene_id="scene5"),
            POI(name="Main Building", lat=59.4645, lng=9.0367, type="building"),
            POI(name="Sculpture Garden", lat=59.4675, lng=9.0397, type="building")
        ]
        for poi in pois:
            db.session.add(poi)
        db.session.commit()
    app.run(host='0.0.0.0', debug=True)
