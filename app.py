from flask import Flask, render_template, send_from_directory

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/projects')
def projects():
    return render_template('projects.html')

@app.route('/blog')
def projects():
    return render_template('blog.html')

@app.route('/resume') # Placeholder for now
def resume():
    return send_from_directory('resume', 'my_resume.pdf')

if __name__ == '__main__':
    app.run(debug=True)
