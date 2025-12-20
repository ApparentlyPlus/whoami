# Whoami?

A terminal-inspired personal portfolio website showcasing my journey as a systems and full-stack developer.

**Live Site**: [whoareyou.plus](https://whoareyou.plus)

## Overview

This is my personal website featuring a cyberpunk-themed design with an interactive terminal emulator. Built with Flask and vanilla JavaScript, it presents my projects, achievements, and professional experience in a unique, developer-friendly interface.

## Features

- **Interactive Terminal**: Landing page with a live-typing terminal emulator showing my background and skills
- **Particle Animation**: Dynamic particle.js background for visual depth
- **Responsive Design**: Fully optimized for desktop, tablet, and mobile devices
- **Project Showcase**: Detailed portfolio of my systems programming and full-stack projects
- **Achievement Gallery**: Comprehensive list of competitive programming, cybersecurity, and academic distinctions

## Tech Stack

### Backend
- **Flask** - Python web framework
- **Jinja2** - Template engine

### Frontend
- **Vanilla JavaScript** - No frameworks, just pure JS
- **Particles.js** - Animated particle background
- **CSS3** - Custom styling with animations
- **JetBrains Mono** - Monospace font for that authentic terminal feel

## Project Structure

```
whoami/
├── static/
│   ├── assets/
│   │   ├── favicon/          # Favicon assets
│   │   └── avatar.jpg        # Profile picture
│   ├── css/
│   │   └── styles.css        # Main stylesheet
│   └── js/
│       └── main.js           # Terminal emulator & interactions
├── templates/
│   ├── base.html             # Base template
│   ├── index.html            # Landing page
│   ├── projects.html         # Projects showcase
│   ├── accolades.html        # Achievements & distinctions
│   ├── real-world-experience.html
│   └── 404.html              # Custom error page
├── resume/
│   └── Chatzikallias_Panagiotis.pdf
├── app.py                    # Flask application
└── passenger_wsgi.py                   # WSGI entry point
```

## Key Pages

- **Home** (`/`) - Interactive terminal with animated bio
- **Projects** (`/projects`) - Featured projects including GatOS, UniNotes, and Marina
- **Accolades** (`/accolades`) - ICPC, ECSC, HTB achievements, and academic excellence
- **Real World Experience** (`/real-world-experience`) - Professional engagements
- **Resume** (`/resume`) - Downloadable PDF

## Installation & Running

### Prerequisites
- Python 3.7+
- pip

### Setup

1. Clone the repository:
```bash
git clone https://github.com/ApparentlyPlus/whoami.git
cd whoami
```

2. Install dependencies:
```bash
pip install requirements.txt
```

3. Run the development server:
```bash
python app.py
```

4. Open your browser and navigate to `http://localhost:5000`

### Production Deployment

For production deployment with a WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn wsgi:app
```

## Design Philosophy

The website embraces a **cyberpunk terminal aesthetic** with:
- Neon green (`#0f0`) accents on dark backgrounds
- Glowing text shadows and hover effects
- Terminal-style command/response interactions
- Minimalist, content-focused layout
- Smooth animations that feel purposeful, not gratuitous

## Customization

To adapt this for your own use:

1. Update personal information in `index.html`
2. Modify terminal commands in `main.js` (search for `startTerminalAnimation`)
3. Replace projects in `projects.html`
4. Update achievements in `accolades.html`
5. Change color scheme in `styles.css` (search for `#0f0` and `#33ff00`)

## Browser Support

- Chrome/Edge (recommended)
- Firefox
- Safari
- Mobile browsers (iOS Safari, Chrome Mobile)

## Performance

- Lightweight: ~100KB total page weight (excluding fonts)
- No heavy frameworks or libraries
- Optimized CSS with minimal reflows
- Efficient particle rendering

## License

This project is open source and available under the MIT License.

## Contact

- **Email**: apparentlyplus@gmail.com
- **GitHub**: [@ApparentlyPlus](https://github.com/ApparentlyPlus)
- **LinkedIn**: [Panagiotis Chatzikallias](https://www.linkedin.com/in/panagiotischatzikallias/)

---

Built with lots of goddamn coffee and late-night coding sessions by [ApparentlyPlus](https://github.com/ApparentlyPlus)