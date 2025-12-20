from flask import Flask, render_template, send_from_directory

app = Flask(__name__)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
    
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/projects')
def projects():
    return render_template('projects.html')

@app.route('/accolades')
def accolades():
    return render_template('accolades.html')

@app.route('/real-world-experience')
def experience():
    return render_template('real-world-experience.html')

@app.route('/resume') # Placeholder for now
def resume():
    return send_from_directory('resume', 'Chatzikallias_Panagiotis.pdf')

if __name__ == '__main__':
    app.run()
