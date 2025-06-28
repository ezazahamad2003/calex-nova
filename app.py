from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import json
import uuid
import logging
from datetime import datetime
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('calex_backend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=['http://localhost:3000'], supports_credentials=True)

# Configuration
UPLOAD_FOLDER = 'data'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'csv', 'json', 'xml', 'xls', 'xlsx', 'md'}

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
logger.info(f"Upload directory created/verified: {UPLOAD_FOLDER}")

# Data storage files
PROJECTS_FILE = os.path.join(UPLOAD_FOLDER, 'projects.json')
GOALS_FILE = os.path.join(UPLOAD_FOLDER, 'goals.json')
INSIGHTS_FILE = os.path.join(UPLOAD_FOLDER, 'insights.json')
FILES_FILE = os.path.join(UPLOAD_FOLDER, 'files.json')

def load_json_data(filename):
    """Load JSON data from file"""
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
    return {}

def save_json_data(filename, data):
    """Save JSON data to file"""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        logger.error(f"Error saving {filename}: {e}")
        return False

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'CALEX Backend is running'})

# Project Management Endpoints
@app.route('/api/projects', methods=['GET'])
def get_projects():
    """Get all projects"""
    try:
        projects = load_json_data(PROJECTS_FILE)
        projects_list = list(projects.values()) if projects else []
        
        # Calculate counts for each project
        goals = load_json_data(GOALS_FILE)
        insights = load_json_data(INSIGHTS_FILE)
        files = load_json_data(FILES_FILE)
        
        for project in projects_list:
            project_id = project['id']
            project['documents_count'] = len([f for f in files.values() if f.get('project_id') == project_id])
            project['goals_count'] = len([g for g in goals.values() if g.get('project_id') == project_id])
            project['insights_count'] = len([i for i in insights.values() if i.get('project_id') == project_id])
            project['research_progress'] = project.get('research_progress', 0)
        
        logger.info(f"Returning {len(projects_list)} projects")
        return jsonify({'projects': projects_list})
    except Exception as e:
        logger.error(f"Error getting projects: {e}")
        return jsonify({'error': 'Failed to get projects'}), 500

@app.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        
        logger.info(f"Creating project: {name}")
        
        if not name:
            return jsonify({'error': 'Project name is required'}), 400
        
        projects = load_json_data(PROJECTS_FILE)
        project_id = str(uuid.uuid4())
        
        project = {
            'id': project_id,
            'name': name,
            'description': description,
            'status': 'setup',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'documents_count': 0,
            'goals_count': 0,
            'insights_count': 0,
            'research_progress': 0
        }
        
        projects[project_id] = project
        save_json_data(PROJECTS_FILE, projects)
        
        logger.info(f"Created project: {name} ({project_id})")
        return jsonify({'project': project}), 201
        
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        return jsonify({'error': 'Failed to create project'}), 500

@app.route('/api/projects/<project_id>/start-research', methods=['POST'])
def start_research(project_id):
    """Start research for a project"""
    try:
        projects = load_json_data(PROJECTS_FILE)
        if project_id not in projects:
            return jsonify({'error': 'Project not found'}), 404
        
        project = projects[project_id]
        project['status'] = 'researching'
        project['updated_at'] = datetime.now().isoformat()
        project['research_progress'] = 0
        
        save_json_data(PROJECTS_FILE, projects)
        
        logger.info(f"Started research for project: {project['name']}")
        return jsonify({'message': 'Research started successfully'})
        
    except Exception as e:
        logger.error(f"Error starting research: {e}")
        return jsonify({'error': 'Failed to start research'}), 500

# File Upload Endpoints
@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload a file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        project_id = request.form.get('project_id')
        
        if not project_id:
            return jsonify({'error': 'Project ID is required'}), 400
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        filename = secure_filename(file.filename)
        file_id = str(uuid.uuid4())
        file_extension = filename.rsplit('.', 1)[1].lower()
        
        # Save file
        file_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
        file.save(file_path)
        
        # Save file metadata
        files = load_json_data(FILES_FILE)
        file_data = {
            'id': file_id,
            'filename': filename,
            'original_name': file.filename,
            'size': os.path.getsize(file_path),
            'type': file.content_type or f'application/{file_extension}',
            'project_id': project_id,
            'upload_date': datetime.now().isoformat(),
            'status': 'completed',
            'path': file_path
        }
        
        files[file_id] = file_data
        save_json_data(FILES_FILE, files)
        
        logger.info(f"Uploaded file: {filename} for project {project_id}")
        return jsonify({'file': file_data})
        
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({'error': 'Failed to upload file'}), 500

@app.route('/api/files', methods=['GET'])
def list_files():
    """List all files"""
    try:
        files = load_json_data(FILES_FILE)
        files_list = list(files.values()) if files else []
        return jsonify({'files': files_list})
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return jsonify({'error': 'Failed to list files'}), 500

@app.route('/api/files/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    """Delete a file"""
    try:
        files = load_json_data(FILES_FILE)
        if file_id not in files:
            return jsonify({'error': 'File not found'}), 404
        
        file_data = files[file_id]
        file_path = file_data.get('path')
        
        # Delete physical file
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        
        # Remove from metadata
        del files[file_id]
        save_json_data(FILES_FILE, files)
        
        logger.info(f"Deleted file: {file_data['filename']}")
        return jsonify({'message': 'File deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        return jsonify({'error': 'Failed to delete file'}), 500

# Goals Endpoints
@app.route('/api/goals/project/<project_id>', methods=['GET'])
def get_project_goals(project_id):
    """Get goals for a project"""
    try:
        goals = load_json_data(GOALS_FILE)
        project_goals = [g for g in goals.values() if g.get('project_id') == project_id]
        return jsonify({'goals': project_goals})
    except Exception as e:
        logger.error(f"Error getting goals: {e}")
        return jsonify({'error': 'Failed to get goals'}), 500

@app.route('/api/goals/project/<project_id>', methods=['POST'])
def create_goal(project_id):
    """Create a new goal for a project"""
    try:
        data = request.get_json()
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        priority = data.get('priority', 'medium')
        
        if not title:
            return jsonify({'error': 'Goal title is required'}), 400
        
        goals = load_json_data(GOALS_FILE)
        goal_id = str(uuid.uuid4())
        
        goal = {
            'id': goal_id,
            'title': title,
            'description': description,
            'priority': priority,
            'status': 'active',
            'project_id': project_id,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'progress': 0
        }
        
        goals[goal_id] = goal
        save_json_data(GOALS_FILE, goals)
        
        logger.info(f"Created goal: {title} for project {project_id}")
        return jsonify({'goal': goal}), 201
        
    except Exception as e:
        logger.error(f"Error creating goal: {e}")
        return jsonify({'error': 'Failed to create goal'}), 500

@app.route('/api/goals/<goal_id>', methods=['PUT'])
def update_goal(goal_id):
    """Update a goal"""
    try:
        data = request.get_json()
        goals = load_json_data(GOALS_FILE)
        
        if goal_id not in goals:
            return jsonify({'error': 'Goal not found'}), 404
        
        goal = goals[goal_id]
        goal.update(data)
        goal['updated_at'] = datetime.now().isoformat()
        
        save_json_data(GOALS_FILE, goals)
        
        logger.info(f"Updated goal: {goal['title']}")
        return jsonify({'goal': goal})
        
    except Exception as e:
        logger.error(f"Error updating goal: {e}")
        return jsonify({'error': 'Failed to update goal'}), 500

@app.route('/api/goals/<goal_id>', methods=['DELETE'])
def delete_goal(goal_id):
    """Delete a goal"""
    try:
        goals = load_json_data(GOALS_FILE)
        
        if goal_id not in goals:
            return jsonify({'error': 'Goal not found'}), 404
        
        goal = goals[goal_id]
        del goals[goal_id]
        save_json_data(GOALS_FILE, goals)
        
        logger.info(f"Deleted goal: {goal['title']}")
        return jsonify({'message': 'Goal deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting goal: {e}")
        return jsonify({'error': 'Failed to delete goal'}), 500

# Insights Endpoints
@app.route('/api/insights/project/<project_id>', methods=['GET'])
def get_project_insights(project_id):
    """Get insights for a project"""
    try:
        insights = load_json_data(INSIGHTS_FILE)
        project_insights = [i for i in insights.values() if i.get('project_id') == project_id]
        return jsonify({'insights': project_insights})
    except Exception as e:
        logger.error(f"Error getting insights: {e}")
        return jsonify({'error': 'Failed to get insights'}), 500

@app.route('/api/insights/project/<project_id>/generate', methods=['POST'])
def generate_insights(project_id):
    """Generate insights for a project"""
    try:
        # Simulate insight generation
        insights = load_json_data(INSIGHTS_FILE)
        
        # Generate sample insights
        sample_insights = [
            {
                'id': str(uuid.uuid4()),
                'content': 'Based on the uploaded documents, there appears to be a strong correlation between market trends and consumer behavior patterns.',
                'insight_type': 'finding',
                'confidence_score': 0.85,
                'relevance_score': 0.92,
                'tags': ['market analysis', 'consumer behavior', 'trends'],
                'project_id': project_id,
                'created_at': datetime.now().isoformat()
            },
            {
                'id': str(uuid.uuid4()),
                'content': 'The data suggests implementing a phased approach to the proposed strategy would minimize risk while maximizing potential returns.',
                'insight_type': 'recommendation',
                'confidence_score': 0.78,
                'relevance_score': 0.88,
                'tags': ['strategy', 'risk management', 'implementation'],
                'project_id': project_id,
                'created_at': datetime.now().isoformat()
            },
            {
                'id': str(uuid.uuid4()),
                'content': 'Further investigation is needed to understand the underlying factors driving these observed patterns.',
                'insight_type': 'question',
                'confidence_score': 0.65,
                'relevance_score': 0.75,
                'tags': ['investigation', 'patterns', 'analysis'],
                'project_id': project_id,
                'created_at': datetime.now().isoformat()
            }
        ]
        
        for insight in sample_insights:
            insights[insight['id']] = insight
        
        save_json_data(INSIGHTS_FILE, insights)
        
        # Update project progress
        projects = load_json_data(PROJECTS_FILE)
        if project_id in projects:
            projects[project_id]['research_progress'] = min(100, projects[project_id].get('research_progress', 0) + 25)
            projects[project_id]['updated_at'] = datetime.now().isoformat()
            save_json_data(PROJECTS_FILE, projects)
        
        logger.info(f"Generated insights for project: {project_id}")
        return jsonify({'message': 'Insights generated successfully'})
        
    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        return jsonify({'error': 'Failed to generate insights'}), 500

# Feedback Endpoints
@app.route('/api/feedback/insight/<insight_id>', methods=['POST'])
def submit_feedback(insight_id):
    """Submit feedback for an insight"""
    try:
        data = request.get_json()
        feedback_type = data.get('feedback_type')
        content = data.get('content')
        
        # In a real implementation, you would save feedback to a database
        logger.info(f"Feedback submitted for insight {insight_id}: {feedback_type}")
        
        return jsonify({'message': 'Feedback submitted successfully'})
        
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        return jsonify({'error': 'Failed to submit feedback'}), 500

# Research Progress Endpoints
@app.route('/api/research/project/<project_id>/live-updates', methods=['GET'])
def get_live_research_updates(project_id):
    """Get live research updates for a project"""
    try:
        # Simulate live research updates
        updates = [
            {
                'id': str(uuid.uuid4()),
                'type': 'web_search',
                'content': 'Searching for recent dark matter research papers on arXiv...',
                'timestamp': datetime.now().isoformat(),
                'status': 'completed',
                'details': {
                    'query': 'dark matter research papers 2024',
                    'sources_found': 12,
                    'relevant_papers': 8
                }
            },
            {
                'id': str(uuid.uuid4()),
                'type': 'analysis',
                'content': 'Analyzing document structure and extracting key concepts...',
                'timestamp': datetime.now().isoformat(),
                'status': 'in_progress',
                'details': {
                    'documents_processed': 3,
                    'concepts_extracted': 45,
                    'relationships_found': 23
                }
            },
            {
                'id': str(uuid.uuid4()),
                'type': 'reasoning',
                'content': 'Identifying patterns in dark matter distribution models...',
                'timestamp': datetime.now().isoformat(),
                'status': 'in_progress',
                'details': {
                    'hypothesis': 'Dark matter clustering shows fractal-like patterns',
                    'confidence': 0.78,
                    'supporting_evidence': 5
                }
            },
            {
                'id': str(uuid.uuid4()),
                'type': 'web_search',
                'content': 'Fetching latest experimental data from CERN...',
                'timestamp': datetime.now().isoformat(),
                'status': 'completed',
                'details': {
                    'query': 'CERN dark matter experiments 2024',
                    'data_sources': ['ATLAS', 'CMS', 'LHCb'],
                    'new_findings': 3
                }
            },
            {
                'id': str(uuid.uuid4()),
                'type': 'insight_generation',
                'content': 'Generating insights based on cross-referenced data...',
                'timestamp': datetime.now().isoformat(),
                'status': 'in_progress',
                'details': {
                    'insights_generated': 2,
                    'confidence_scores': [0.85, 0.72],
                    'next_steps': ['Validate with additional datasets', 'Compare with theoretical models']
                }
            }
        ]
        
        return jsonify({'updates': updates})
        
    except Exception as e:
        logger.error(f"Error getting live updates: {e}")
        return jsonify({'error': 'Failed to get live updates'}), 500

@app.route('/api/research/project/<project_id>/start-live', methods=['POST'])
def start_live_research(project_id):
    """Start live research with real-time updates"""
    try:
        # Update project status
        projects = load_json_data(PROJECTS_FILE)
        if project_id not in projects:
            return jsonify({'error': 'Project not found'}), 404
        
        project = projects[project_id]
        project['status'] = 'researching'
        project['updated_at'] = datetime.now().isoformat()
        project['research_progress'] = 0
        project['live_research_started'] = True
        
        save_json_data(PROJECTS_FILE, projects)
        
        logger.info(f"Started live research for project: {project['name']}")
        return jsonify({'message': 'Live research started successfully'})
        
    except Exception as e:
        logger.error(f"Error starting live research: {e}")
        return jsonify({'error': 'Failed to start live research'}), 500

# Advanced Research Endpoints
@app.route('/api/research/project/<project_id>/advanced-live', methods=['GET'])
def get_advanced_live_research(project_id):
    """Get advanced live research with branching threads and AI interactions"""
    try:
        # Simulate advanced research with branching threads
        research_data = {
            'main_thread': {
                'id': 'main-001',
                'status': 'active',
                'focus': 'Self-healing polymer composites for space applications',
                'progress': 65,
                'start_time': datetime.now().isoformat(),
                'updates': [
                    {
                        'id': str(uuid.uuid4()),
                        'timestamp': '0:00',
                        'type': 'analysis_start',
                        'content': 'Analyzing uploaded documents: 3 NASA whitepapers, 2 academic PDFs, 1 video lecture transcript.',
                        'ai_message': True,
                        'details': {
                            'documents_analyzed': 6,
                            'key_topics': ['self-healing materials', 'space applications', 'polymer composites']
                        }
                    },
                    {
                        'id': str(uuid.uuid4()),
                        'timestamp': '0:03',
                        'type': 'insight',
                        'content': 'Self-healing polymer composites show micro-crack repair under vacuum. Most recent success: ESA 2024 test on ISS.',
                        'ai_message': True,
                        'confidence': 0.92,
                        'references': ['ESA_2024_ISS_Report.pdf'],
                        'details': {
                            'key_limitations': ['slow healing at low temperatures'],
                            'success_rate': '78%',
                            'temperature_range': '-40°C to +60°C'
                        }
                    },
                    {
                        'id': str(uuid.uuid4()),
                        'timestamp': '0:09',
                        'type': 'discovery',
                        'content': 'Detected missing data: No current solution for micrometeorite punctures in rigid modules.',
                        'ai_message': True,
                        'requires_action': True,
                        'suggestions': [
                            {'action': 'pivot', 'label': 'Pivot to rapid-response materials', 'confidence': 0.85},
                            {'action': 'continue', 'label': 'Keep original focus', 'confidence': 0.60},
                            {'action': 'discuss', 'label': 'Discuss options', 'confidence': 0.75}
                        ]
                    }
                ]
            },
            'branch_threads': [
                {
                    'id': 'branch-001',
                    'parent_id': 'main-001',
                    'status': 'active',
                    'focus': 'Smart foams for impact absorption',
                    'progress': 40,
                    'start_time': datetime.now().isoformat(),
                    'trigger': 'User selected pivot to rapid-response materials',
                    'updates': [
                        {
                            'id': str(uuid.uuid4()),
                            'timestamp': '0:16',
                            'type': 'branch_created',
                            'content': 'Launching sub-research group: Smart foams for impact absorption',
                            'ai_message': True,
                            'details': {
                                'documents_to_analyze': 4,
                                'external_sources': ['SpaceX blog posts', 'MIT research database'],
                                'estimated_completion': '15 minutes'
                            }
                        },
                        {
                            'id': str(uuid.uuid4()),
                            'timestamp': '0:22',
                            'type': 'live_update',
                            'content': 'Smart foam prototypes (MIT, 2023) demonstrated 40% faster sealing than traditional layers.',
                            'ai_message': True,
                            'details': {
                                'researchers_identified': ['Dr. Sarah Chen', 'Prof. Michael Rodriguez'],
                                'suggested_action': 'outreach',
                                'contact_info_available': True
                            }
                        }
                    ]
                }
            ],
            'completed_threads': [],
            'pending_actions': [
                {
                    'id': str(uuid.uuid4()),
                    'type': 'user_decision',
                    'content': 'Choose research direction for micrometeorite protection',
                    'options': ['pivot', 'continue', 'discuss'],
                    'deadline': None,
                    'priority': 'high'
                }
            ]
        }
        
        return jsonify(research_data)
        
    except Exception as e:
        logger.error(f"Error getting advanced research: {e}")
        return jsonify({'error': 'Failed to get advanced research'}), 500

@app.route('/api/research/project/<project_id>/action', methods=['POST'])
def handle_research_action(project_id):
    """Handle user actions in research (pivot, continue, discuss, etc.)"""
    try:
        data = request.get_json()
        action_type = data.get('action_type')
        action_data = data.get('action_data', {})
        
        logger.info(f"Research action for project {project_id}: {action_type}")
        
        # Simulate action processing
        response_data = {
            'action_processed': True,
            'new_branch_created': action_type == 'pivot',
            'main_thread_updated': True,
            'next_update': {
                'timestamp': datetime.now().strftime('%M:%S'),
                'content': f'Action "{action_type}" processed. Research direction updated.',
                'ai_message': True
            }
        }
        
        if action_type == 'pivot':
            response_data['branch_info'] = {
                'id': f'branch-{str(uuid.uuid4())[:8]}',
                'focus': action_data.get('new_focus', 'New research direction'),
                'estimated_duration': '10-15 minutes'
            }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error handling research action: {e}")
        return jsonify({'error': 'Failed to process action'}), 500

@app.route('/api/research/project/<project_id>/stream', methods=['GET'])
def stream_research_updates(project_id):
    """Stream real-time research updates (simulated)"""
    try:
        # Simulate streaming updates
        updates = [
            {
                'timestamp': datetime.now().strftime('%M:%S'),
                'type': 'analysis',
                'content': 'Processing document 4 of 6: "Advanced Materials for Space Applications"',
                'progress': 67
            },
            {
                'timestamp': datetime.now().strftime('%M:%S'),
                'type': 'web_search',
                'content': 'Found 3 new research papers on smart materials from 2024',
                'progress': 75
            },
            {
                'timestamp': datetime.now().strftime('%M:%S'),
                'type': 'insight',
                'content': 'Cross-referencing reveals potential for hybrid self-healing/impact materials',
                'progress': 82
            }
        ]
        
        return jsonify({'updates': updates})
        
    except Exception as e:
        logger.error(f"Error streaming updates: {e}")
        return jsonify({'error': 'Failed to stream updates'}), 500

if __name__ == '__main__':
    print("Starting CALEX Flask Backend...")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print("Available endpoints:")
    print("  GET  /health - Health check")
    print("  GET  /api/projects - List projects")
    print("  POST /api/projects - Create project")
    print("  POST /api/projects/<id>/start-research - Start research")
    print("  POST /api/upload - Upload file")
    print("  GET  /api/files - List files")
    print("  DELETE /api/files/<id> - Delete file")
    print("  GET  /api/goals/project/<id> - Get project goals")
    print("  POST /api/goals/project/<id> - Create goal")
    print("  GET  /api/insights/project/<id> - Get project insights")
    print("  POST /api/insights/project/<id>/generate - Generate insights")
    print("  GET  /api/research/project/<id>/live-updates - Get live research updates")
    print("  POST /api/research/project/<id>/start-live - Start live research")
    print("  GET  /api/research/project/<id>/advanced-live - Get advanced live research")
    print("  POST /api/research/project/<id>/action - Handle research action")
    print("  GET  /api/research/project/<id>/stream - Stream research updates")
    print("Server starting on http://localhost:5000")
    print("Logs will be saved to calex_backend.log")
    
    logger.info("CALEX Flask Backend starting up")
    app.run(host='0.0.0.0', port=5000, debug=True) 