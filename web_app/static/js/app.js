const connectButton = document.getElementById('connect-button');
const generateSessionButton = document.getElementById('generate-session-button');
const startInterviewButton = document.getElementById('start-interview-button');
const linkDeviceButton = document.getElementById('link-device-button');
const createFirstSessionButton = document.getElementById('create-first-session-button');
const sessionInput = document.getElementById('session-id');
const pairingCodeLine = document.getElementById('pairing-code-line');
const statusLine = document.getElementById('status-line');
const snapshotCard = document.getElementById('snapshot-card');
const companyName = document.getElementById('company-name');
const roleTitle = document.getElementById('role-title');
const overlayStatus = document.getElementById('overlay-status');
const callState = document.getElementById('call-state');
const turnCount = document.getElementById('turn-count');
const callerName = document.getElementById('caller-name');
const callerStageCopy = document.getElementById('caller-stage-copy');
const meetingSourceChip = document.getElementById('meeting-source-chip');
const meetingCaptureChip = document.getElementById('meeting-capture-chip');
const cameraLayoutCopy = document.getElementById('camera-layout-copy');
const companyChip = document.getElementById('company-chip');
const roleChip = document.getElementById('role-chip');
const candidateChip = document.getElementById('candidate-chip');
const headline = document.getElementById('headline');
const transcriptSummary = document.getElementById('transcript-summary');
const timelineList = document.getElementById('timeline-list');
const historyList = document.getElementById('history-list');
const historyStatus = document.getElementById('history-status');
const body = document.getElementById('body');
const confidenceScore = document.getElementById('confidence-score');
const workerStatus = document.getElementById('worker-status');
const updatedAt = document.getElementById('updated-at');
const providerStatus = document.getElementById('provider-status');
const workspaceMode = document.getElementById('workspace-mode');
const microphoneMode = document.getElementById('microphone-mode');
const readinessTitle = document.getElementById('readiness-title');
const readinessHint = document.getElementById('readiness-hint');
const alternativesList = document.getElementById('alternatives-list');
const actionGrid = document.getElementById('action-grid');
const recentSessions = document.getElementById('recent-sessions');
const persistentPrompt = document.getElementById('persistent-prompt');
const livePrompt = document.getElementById('live-prompt');
const savePromptsButton = document.getElementById('save-prompts-button');
const clearPromptsButton = document.getElementById('clear-prompts-button');
const promptStatus = document.getElementById('prompt-status');
const promptChips = Array.from(document.querySelectorAll('.prompt-chip'));
const wizardStepper = document.getElementById('wizard-stepper');
const wizardSteps = Array.from(document.querySelectorAll('.wizard-step'));
const wizardTitle = document.getElementById('wizard-title');
const wizardStepLabel = document.getElementById('wizard-step-label');
const wizardStatus = document.getElementById('wizard-status');
const wizardBackButton = document.getElementById('wizard-back-button');
const wizardNextButton = document.getElementById('wizard-next-button');
const wizardQuickStartButton = document.getElementById('wizard-quick-start-button');
const wizardSaveButton = document.getElementById('wizard-save-button');
const microphoneBanner = document.getElementById('microphone-banner');
const wizardAlignmentRole = document.getElementById('wizard-alignment-role');
const wizardAlignmentProof = document.getElementById('wizard-alignment-proof');
const wizardAlignmentMeeting = document.getElementById('wizard-alignment-meeting');
const wizardAlignmentTone = document.getElementById('wizard-alignment-tone');
const alignmentIdentity = document.getElementById('alignment-identity');
const alignmentProof = document.getElementById('alignment-proof');
const alignmentMeeting = document.getElementById('alignment-meeting');
const alignmentTone = document.getElementById('alignment-tone');
const sectionNav = document.querySelector('.section-nav');
const sectionNavLinks = Array.from(document.querySelectorAll('.section-nav__link'));
const sectionNavCurrent = document.getElementById('section-nav-current');

function slugifySessionSegment(value, fallback) {
  const normalized = String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return normalized || fallback;
}

function generateSessionId() {
  const name = slugifySessionSegment(briefingFields.full_name?.value, 'candidate');
  const company = slugifySessionSegment(briefingFields.company_name?.value, 'company');
  const role = slugifySessionSegment(
    briefingFields.target_role?.value || briefingFields.current_role?.value,
    'role',
  );
  const now = new Date();
  const timestamp = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
    String(now.getHours()).padStart(2, '0'),
    String(now.getMinutes()).padStart(2, '0'),
    String(now.getSeconds()).padStart(2, '0'),
  ].join('');
  return `${name}-${company}-${role}-${timestamp}`;
}

function renderStatusIndicator(element, label, tone, pulse = false) {
  if (element === null) {
    return;
  }
  element.className = `status-indicator status-indicator--${tone}${pulse ? ' status-indicator--pulse' : ''}`;
  let labelNode = element.querySelector('.status-indicator__label');
  if (labelNode === null) {
    element.innerHTML = '<span class="status-indicator__dot" aria-hidden="true"></span><span class="status-indicator__label"></span>';
    labelNode = element.querySelector('.status-indicator__label');
  }
  if (labelNode !== null) {
    labelNode.textContent = label;
  }
}

function updateProviderIndicator(providerLabel) {
  const normalized = String(providerLabel || '').trim();
  const disconnected = !normalized || /not connected|not reported|unavailable|offline/i.test(normalized);
  renderStatusIndicator(
    providerStatus,
    disconnected ? 'Not connected' : 'Connected',
    disconnected ? 'disconnected' : 'connected',
  );
}

function updateWorkspaceModeIndicator(modeLabel) {
  const normalized = String(modeLabel || 'standby').toLowerCase();
  if (normalized.includes('answer_ready') || normalized.includes('ready')) {
    renderStatusIndicator(workspaceMode, 'ready', 'ready', true);
    return;
  }
  if (normalized.includes('listening')) {
    renderStatusIndicator(workspaceMode, 'listening', 'listening', true);
    return;
  }
  if (normalized.includes('armed') || normalized.includes('active')) {
    renderStatusIndicator(workspaceMode, 'active', 'active', true);
    return;
  }
  renderStatusIndicator(workspaceMode, 'standby', 'standby');
}

function applyGeneratedSessionId() {
  const sessionId = generateSessionId();
  sessionInput.value = sessionId;
  statusLine.textContent = `Generated session ID: ${sessionId}`;
  statusLine.classList.remove('error');
  sessionInput.focus();
  sessionInput.setSelectionRange(0, sessionInput.value.length);
  return sessionId;
}

let currentSessionId = '';
let refreshTimer = null;
let eventSource = null;
let currentWizardStep = 0;
let activeSectionId = 'command-deck';

const wizardModel = [
  { title: 'Who you are', description: 'Upload resume, name, role, location.' },
  { title: 'Skills & Experience', description: 'Skills, proof points, achievements.' },
  { title: 'Target role & style', description: 'Target job, interview platform, answer style.' },
];

const sectionModel = sectionNavLinks
  .map((link) => {
    const panel = document.getElementById(link.dataset.sectionTarget || '');
    if (panel === null) {
      return null;
    }
    return {
      link,
      panel,
      id: panel.id,
      name: panel.dataset.sectionName || link.textContent.trim(),
    };
  })
  .filter(Boolean);

function updateSectionNavMeta() {
  const activeSection = sectionModel.find((section) => section.id === activeSectionId) || sectionModel[0] || null;
  if (activeSection !== null && sectionNavCurrent !== null) {
    sectionNavCurrent.textContent = activeSection.name;
  }
}

function setActiveSection(sectionId) {
  activeSectionId = sectionId;
  sectionModel.forEach((section) => {
    const isActive = section.id === sectionId;
    section.link.classList.toggle('active', isActive);
    section.panel.classList.toggle('section-in-view', isActive);
  });
  updateSectionNavMeta();
}

function initializeSectionNav() {
  if (!sectionModel.length) {
    return;
  }

  sectionModel.forEach((section) => {
    section.link.addEventListener('click', (event) => {
      event.preventDefault();
      section.panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setActiveSection(section.id);
    });
  });

  if (typeof IntersectionObserver === 'undefined') {
    setActiveSection(sectionModel[0].id);
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      const visibleEntries = entries
        .filter((entry) => entry.isIntersecting)
        .sort((left, right) => right.intersectionRatio - left.intersectionRatio);

      if (!visibleEntries.length) {
        return;
      }

      const leading = visibleEntries[0].target;
      if (!(leading instanceof HTMLElement)) {
        return;
      }
      setActiveSection(leading.id);
    },
    {
      rootMargin: '-24% 0px -48% 0px',
      threshold: [0.2, 0.35, 0.55, 0.7],
    },
  );

  sectionModel.forEach((section) => {
    observer.observe(section.panel);
  });

  setActiveSection(sectionModel[0].id);
}

// ─────────────────────────────────────────────────────────────────────────────
// COMBOBOX DROPDOWN DATA — freelancer-first options for every field
// Custom values added by the user are persisted in localStorage under the
// same key so they survive refreshes.
// ─────────────────────────────────────────────────────────────────────────────
const COMBOBOX_DEFAULTS = {
  'current-role': [
    // Development
    'Full-Stack Developer','Frontend Developer','Backend Developer',
    'React Developer','Vue.js Developer','Angular Developer','Next.js Developer',
    'Node.js Developer','Python Developer','Django Developer','FastAPI Developer',
    'Laravel / PHP Developer','Ruby on Rails Developer','ASP.NET Developer',
    'WordPress Developer','Shopify Developer','WooCommerce Developer','Webflow Developer',
    // Mobile
    'Flutter Developer','React Native Developer','Android Developer (Kotlin/Java)',
    'iOS Developer (Swift)','Cross-platform Mobile Developer',
    // Cloud / DevOps
    'DevOps Engineer','Cloud Engineer (AWS)','Cloud Engineer (Azure)','Cloud Engineer (GCP)',
    'Site Reliability Engineer (SRE)','Linux System Administrator',
    'Docker / Kubernetes Engineer','CI/CD Engineer',
    // Data / AI
    'Data Scientist','Data Analyst','Machine Learning Engineer','AI / LLM Engineer',
    'Prompt Engineer','NLP Engineer','Computer Vision Engineer',
    'Business Intelligence Developer','Power BI Developer','Tableau Developer',
    // Design
    'UI/UX Designer','Product Designer','Figma Designer',
    'Graphic Designer','Logo & Brand Designer','Motion / Animation Designer',
    'Web Designer','Illustration Artist',
    // Marketing & Content
    'SEO Specialist','Digital Marketing Expert','PPC / Google Ads Specialist',
    'Facebook / Meta Ads Specialist','Content Writer','Technical Writer',
    'Copywriter','Email Marketing Specialist','Social Media Manager',
    // Video & Media
    'Video Editor','YouTube Content Creator','Podcast Producer',
    'Voice-over Artist','3D Animator','Videographer',
    // Other Tech
    'QA / Test Engineer','Cybersecurity Analyst','Blockchain Developer',
    'Smart Contract Developer (Solidity)','Game Developer (Unity)','Game Developer (Unreal)',
    'Embedded Systems Engineer','IoT Developer',
    // Management & Consulting
    'Technical Project Manager','Scrum Master','Product Manager',
    'Business Analyst','IT Consultant','ERP Consultant (SAP/Oracle)',
    'CRM Consultant (Salesforce/HubSpot)','Digital Transformation Consultant',
    // Finance
    'Accountant / Bookkeeper','QuickBooks Specialist','Xero Accountant',
    'Virtual CFO','Financial Modeler',
  ],
  'location': [
    // Pakistan
    'Lahore, Pakistan','Karachi, Pakistan','Islamabad, Pakistan',
    'Rawalpindi, Pakistan','Faisalabad, Pakistan','Multan, Pakistan',
    'Peshawar, Pakistan','Quetta, Pakistan','Sialkot, Pakistan','Gujranwala, Pakistan',
    'Remote (Pakistan)','Remote (PKT – UTC+5)',
    // Middle East
    'Dubai, UAE','Abu Dhabi, UAE','Sharjah, UAE',
    'Riyadh, Saudi Arabia','Jeddah, Saudi Arabia','Doha, Qatar',
    'Kuwait City, Kuwait','Muscat, Oman','Manama, Bahrain',
    // South Asia
    'Mumbai, India','Delhi, India','Bangalore, India','Hyderabad, India',
    'Colombo, Sri Lanka','Dhaka, Bangladesh','Kathmandu, Nepal',
    // UK & Europe
    'London, UK','Manchester, UK','Birmingham, UK',
    'Berlin, Germany','Munich, Germany','Frankfurt, Germany',
    'Amsterdam, Netherlands','Paris, France','Stockholm, Sweden','Zurich, Switzerland',
    // North America
    'New York, USA','San Francisco, USA','Austin, USA','Toronto, Canada','Vancouver, Canada',
    // Australia & Asia
    'Sydney, Australia','Melbourne, Australia','Singapore','Kuala Lumpur, Malaysia',
    // Remote global
    'Remote (Worldwide)','Remote (US hours)','Remote (EU hours)','Remote (APAC hours)',
    'Open to relocation',
  ],
  'work-mode': [
    'Remote — full time','Remote — part time','Remote — contract / project-based',
    'Hybrid (2–3 days office)','Hybrid (flexible)','On-site — full time',
    'Freelance / independent contractor','Upwork / Fiverr platform projects',
    'Agency model (sub-contractor)','Open to any arrangement',
  ],
  'industry': [
    'IT / Software Development','SaaS / Product Company','Freelancing / Consulting',
    'E-commerce / Retail Tech','Digital Marketing & Advertising','UI/UX & Design',
    'FinTech / Banking','HealthTech / MedTech','EdTech / Online Learning',
    'Real Estate / PropTech','Logistics / Supply Chain / WMS',
    'Media & Entertainment','Gaming & Interactive','Legal / LegalTech',
    'HR Tech / Recruitment','Travel & Hospitality Tech','AgriTech','CleanTech / GreenTech',
    'AI / Machine Learning Products','Cybersecurity','Blockchain / Web3 / DeFi',
    'Government / Public Sector','Non-profit / NGO',
    'Telecom / ISP','Insurance / InsurTech',
  ],
  'skills': [
    // Web frontend
    'HTML5','CSS3','JavaScript (ES2020+)','TypeScript','React','Vue.js','Angular',
    'Next.js','Nuxt.js','Svelte','jQuery','Tailwind CSS','Bootstrap','Sass/SCSS',
    // Web backend
    'Python','Django','FastAPI','Flask','Node.js','Express.js','NestJS',
    'PHP','Laravel','Symfony','Ruby on Rails','Java','Spring Boot',
    'C#','.NET','ASP.NET Core','Go (Golang)','Rust',
    // Mobile
    'Flutter','Dart','React Native','Swift','SwiftUI','Kotlin','Android SDK','Expo',
    // Databases
    'PostgreSQL','MySQL','SQLite','MongoDB','Redis','Firebase Realtime DB',
    'Supabase','DynamoDB','Elasticsearch','Cassandra','ClickHouse',
    // Cloud & DevOps
    'AWS (EC2/S3/Lambda/RDS)','Azure','Google Cloud Platform','Firebase',
    'Docker','Kubernetes','Terraform','Ansible','GitHub Actions','GitLab CI',
    'CircleCI','Jenkins','Nginx','Linux (Ubuntu/CentOS)',
    // APIs & Architecture
    'REST API Design','GraphQL','WebSockets','gRPC','Microservices',
    'Event-driven Architecture','RabbitMQ','Apache Kafka',
    // Data & AI
    'Python (Data Science)','Pandas','NumPy','Matplotlib','Jupyter',
    'Machine Learning','Scikit-learn','TensorFlow','PyTorch','Keras',
    'OpenAI API','LangChain','Hugging Face','RAG Systems','Prompt Engineering',
    'SQL Analytics','Power BI','Tableau','Google Data Studio','Looker',
    // Design
    'Figma','Adobe XD','Photoshop','Illustrator','After Effects','Premiere Pro',
    'UI Design','UX Research','Wireframing','Prototyping','Design Systems',
    // Marketing
    'SEO','Google Ads','Meta / Facebook Ads','TikTok Ads',
    'Email Marketing','Mailchimp','HubSpot','ActiveCampaign',
    'Copywriting','Content Strategy','Social Media Marketing',
    // Testing & QA
    'Jest','Pytest','Selenium','Cypress','Playwright','Postman','k6',
    // Management & Soft
    'Agile / Scrum','Jira','Trello','Notion','Project Management',
    'Client Communication','Technical Documentation','Code Review',
    'Team Leadership','Mentoring',
    // Others
    'WordPress','Shopify / Liquid','WooCommerce','Webflow','Wix',
    'Git','GitHub','Bitbucket','CI/CD','Unit Testing','TDD','API Integration',
  ],
  'tech': [
    'React + TypeScript','Next.js + Tailwind','Vue 3 + Pinia',
    'Python + FastAPI','Python + Django REST','Node.js + Express',
    'Node.js + NestJS','Laravel + MySQL','Ruby on Rails',
    'Flutter + Firebase','React Native + Expo',
    'PostgreSQL','MySQL','MongoDB','Redis','Supabase','Firebase',
    'Docker + Kubernetes','AWS (EC2 / S3 / Lambda)','Azure App Service',
    'Google Cloud Run','Vercel / Netlify',
    'GraphQL + Apollo','REST APIs','WebSockets',
    'TensorFlow / Keras','PyTorch','OpenAI API','LangChain',
    'Figma','Tailwind CSS','Bootstrap 5',
    'Stripe / PayPal API','Twilio','SendGrid','Pusher',
    'WordPress + WooCommerce','Shopify / Liquid',
    'Git + GitHub Actions','GitLab CI',
  ],
  'reason-for-change': [
    'Looking for a higher hourly rate / salary',
    'Seeking larger or more complex projects',
    'Want to move from freelance to full-time employment',
    'Want to move from full-time to freelance',
    'Career growth — targeting a senior / lead role',
    'Switching technology stack / domain',
    'Contract / project ended naturally',
    'Client budget cut / company restructuring',
    'Seeking better work-life balance',
    'Relocating to a new city or country',
    'Looking for a remote-first opportunity',
    'Interested in a product company (from agency)',
    'Interested in a startup (from corporate)',
    'Interested in AI / ML focused work',
    'Building my own client base / brand',
    'Expanding to international clients',
    'Current role does not offer learning opportunities',
    'Toxic work environment / culture mismatch',
    'Family reasons / personal circumstances',
  ],
  'salary': [
    // Hourly (freelance)
    '$5/hr','$8/hr','$10/hr','$12/hr','$15/hr','$18/hr','$20/hr',
    '$25/hr','$30/hr','$35/hr','$40/hr','$50/hr','$60/hr',
    '$75/hr','$100/hr','$120/hr','$150/hr','$200/hr',
    // Project-based
    '$200/project','$500/project','$1,000/project','$2,000/project',
    '$3,000/project','$5,000/project','$10,000/project',
    // Monthly retainer / salary
    'PKR 80,000/mo','PKR 100,000/mo','PKR 150,000/mo','PKR 200,000/mo',
    '$800/mo','$1,000/mo','$1,500/mo','$2,000/mo','$2,500/mo',
    '$3,000/mo','$4,000/mo','$5,000/mo','$6,000/mo','$8,000/mo',
    // Annual
    '$30k/yr','$40k/yr','$50k/yr','$60k/yr','$70k/yr','$80k/yr',
    '$90k/yr','$100k/yr','$120k/yr','$150k/yr',
    // Flexible
    'Negotiable — depends on scope','Market rate','Open to discussion',
    'Equity + salary (startup)','Revenue share model',
  ],
  'company-type': [
    'Startup (seed / pre-A)','Startup (Series A+)','Scale-up','Unicorn',
    'SME (Small & Medium Enterprise)','Corporate / Enterprise','Government / Public Sector',
    'Agency (digital / creative)','Consulting / IT services firm',
    'Product company (SaaS / B2B)','E-commerce brand',
    'Freelance direct client','Marketplace client (Upwork / Fiverr / Toptal)',
    'Remote-first company','Non-profit / NGO','Educational institution',
  ],
  'interview-difficulty': [
    'Junior (0–2 years)','Mid-level (2–5 years)','Senior (5–8 years)',
    'Lead / Principal (8+ years)','Architect level',
    'Freelance screening call','Client discovery call',
    'Technical round (live coding)','System design round',
    'Portfolio / work review','Paid trial project',
    'Culture / behavioural fit round','HR / final round',
  ],
  'meeting-source': [
    'Zoom','Google Meet','Microsoft Teams','WhatsApp Desktop',
    'Skype','Slack Huddle','Discord','Webex',
    'GoToMeeting','BlueJeans','Whereby','Jitsi Meet',
    'Phone call (audio only)','In-person interview',
    'Manual / generic interview','Email-based async interview',
  ],
  'capture-mode': [
    'Companion workspace with live mic capture',
    'Screen companion only (no mic — type questions manually)',
    'Scripted question entry (paste expected questions)',
    'WhatsApp / phone call companion',
    'Dual-screen setup (main + copilot)',
    'Headphone monitoring only',
  ],
  'answer-style': [
    'Simple English — concise, confident, humble',
    'STAR method — Situation, Task, Action, Result',
    'PAR method — Problem, Action, Result',
    'Bullet-point concise — 3 key points max',
    'Narrative storytelling — vivid and engaging',
    'Formal and professional — no contractions',
    'Casual and friendly — approachable tone',
    'Technical precision — use exact domain terms',
    'Conversational — avoid buzzwords and jargon',
    'Leadership-focused — emphasise impact and ownership',
    'Freelancer-focused — emphasise autonomy and delivery',
    'Client-friendly — results and ROI focused',
  ],
};

const COMBOBOX_STORAGE_KEY = 'career-copilot:combobox-custom';

function loadCustomComboboxValues() {
  try {
    return JSON.parse(localStorage.getItem(COMBOBOX_STORAGE_KEY) || '{}');
  } catch {
    return {};
  }
}

function saveCustomComboboxValues(data) {
  localStorage.setItem(COMBOBOX_STORAGE_KEY, JSON.stringify(data));
}

function getComboboxOptions(key) {
  const defaults = COMBOBOX_DEFAULTS[key] || [];
  const custom = loadCustomComboboxValues()[key] || [];
  return [...custom, ...defaults];
}

function addCustomComboboxValue(key, value) {
  const data = loadCustomComboboxValues();
  if (!data[key]) data[key] = [];
  const trimmed = value.trim();
  if (!trimmed || data[key].includes(trimmed)) return;
  data[key].unshift(trimmed);
  saveCustomComboboxValues(data);
}

// ─────────────────────────────────────────────────────────────────────────────
// COMBOBOX WIDGET INIT
// ─────────────────────────────────────────────────────────────────────────────
function initCombobox(shell) {
  const key = shell.dataset.key || '';
  const fieldId = shell.dataset.field || '';
  const inputEl = shell.querySelector('input[type="text"]');
  const listEl = shell.querySelector('.combobox-list');
  const toggleBtn = shell.querySelector('.combobox-toggle');
  const tagsContainer = shell.querySelector('.combobox-tags');
  const hiddenInput = tagsContainer ? shell.querySelector('input[type="hidden"]') : null;
  const isTags = Boolean(tagsContainer);

  if (!inputEl || !listEl) return;

  let selectedTags = [];

  function getTagsFromHidden() {
    return hiddenInput
      ? hiddenInput.value.split(',').map(v => v.trim()).filter(Boolean)
      : [];
  }

  function refreshTagsUI() {
    if (!tagsContainer) return;
    tagsContainer.innerHTML = '';
    selectedTags.forEach((tag, i) => {
      const chip = document.createElement('span');
      chip.className = 'combobox-tag';
      chip.innerHTML = `${tag} <button type="button" data-i="${i}" aria-label="Remove ${tag}">×</button>`;
      chip.querySelector('button').addEventListener('click', () => {
        selectedTags.splice(i, 1);
        if (hiddenInput) hiddenInput.value = selectedTags.join(', ');
        refreshTagsUI();
        renderWizardAlignment();
      });
      tagsContainer.appendChild(chip);
    });
    if (hiddenInput) hiddenInput.value = selectedTags.join(', ');
  }

  function buildList(filter = '') {
    const options = getComboboxOptions(key);
    const lf = filter.toLowerCase();
    const filtered = options.filter(o => !lf || o.toLowerCase().includes(lf));
    listEl.innerHTML = '';

    if (filter && !options.find(o => o.toLowerCase() === filter.toLowerCase())) {
      const addLi = document.createElement('li');
      addLi.className = 'combobox-option combobox-option--add';
      addLi.textContent = `+ Add "${filter}"`;
      addLi.addEventListener('mousedown', (e) => {
        e.preventDefault();
        const val = filter.trim();
        addCustomComboboxValue(key, val);
        if (isTags) {
          if (val && !selectedTags.includes(val)) {
            selectedTags.push(val);
            refreshTagsUI();
          }
          inputEl.value = '';
        } else {
          inputEl.value = val;
          if (!isTags) { inputEl.dispatchEvent(new Event('input', { bubbles: true })); }
        }
        closeList();
        renderWizardAlignment();
      });
      listEl.appendChild(addLi);
    }

    filtered.slice(0, 30).forEach(option => {
      const li = document.createElement('li');
      li.className = 'combobox-option';
      const isSelected = isTags ? selectedTags.includes(option) : false;
      if (isSelected) li.classList.add('selected');
      li.textContent = option;
      li.addEventListener('mousedown', (e) => {
        e.preventDefault();
        if (isTags) {
          if (!selectedTags.includes(option)) {
            selectedTags.push(option);
            refreshTagsUI();
          }
          inputEl.value = '';
        } else {
          inputEl.value = option;
          inputEl.dispatchEvent(new Event('input', { bubbles: true }));
        }
        closeList();
        renderWizardAlignment();
      });
      listEl.appendChild(li);
    });

    listEl.classList.toggle('hidden', listEl.children.length === 0);
  }

  function openList() {
    buildList(inputEl.value);
    listEl.classList.remove('hidden');
  }

  function closeList() {
    listEl.classList.add('hidden');
  }

  inputEl.addEventListener('focus', () => openList());
  inputEl.addEventListener('input', () => buildList(inputEl.value));
  inputEl.addEventListener('blur', () => setTimeout(closeList, 150));
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const val = inputEl.value.trim();
      if (!val) return;
      if (isTags) {
        if (!selectedTags.includes(val)) {
          addCustomComboboxValue(key, val);
          selectedTags.push(val);
          refreshTagsUI();
        }
        inputEl.value = '';
      } else {
        addCustomComboboxValue(key, val);
      }
      closeList();
      renderWizardAlignment();
    }
    if (e.key === 'Escape') closeList();
  });

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      if (listEl.classList.contains('hidden')) {
        openList();
        inputEl.focus();
      } else {
        closeList();
      }
    });
  }

  if (isTags) {
    selectedTags = getTagsFromHidden();
    refreshTagsUI();
  }
}

function initAllComboboxes() {
  document.querySelectorAll('.combobox-shell').forEach(shell => initCombobox(shell));
}

// ─────────────────────────────────────────────────────────────────────────────
// RESUME FILE BROWSE + EXTRACT
// ─────────────────────────────────────────────────────────────────────────────
function initResumeBrowse() {
  const browseBtn = document.getElementById('brief-resume-browse');
  const fileInput = document.getElementById('brief-resume-file-input');
  const fileLabel = document.getElementById('brief-resume-file-name');
  const extractBtn = document.getElementById('brief-resume-extract');
  const resumeText = document.getElementById('brief-resume-text');
  const resumeFilename = document.getElementById('brief-resume-filename');

  if (!browseBtn || !fileInput) return;

  browseBtn.addEventListener('click', () => fileInput.click());

  fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    if (!file) return;
    fileLabel.textContent = file.name;
    if (resumeFilename) resumeFilename.value = file.name;
    extractBtn.disabled = false;
    extractBtn.textContent = 'Extract text';
  });

  extractBtn.addEventListener('click', async () => {
    const file = fileInput.files[0];
    if (!file) return;

    extractBtn.disabled = true;
    extractBtn.textContent = 'Extracting…';

    try {
      const ext = file.name.split('.').pop().toLowerCase();
      if (ext === 'txt') {
        const text = await file.text();
        if (resumeText) resumeText.value = text;
        extractBtn.textContent = '✓ Done';
      } else {
        const formData = new FormData();
        formData.append('resume', file);
        const resp = await fetch('/api/resume/extract', { method: 'POST', body: formData });
        const result = await resp.json();
        if (!resp.ok) throw new Error(result.error || 'Extraction failed');
        if (resumeText) resumeText.value = result.text || '';
        if (result.skills && !document.getElementById('brief-skills')?.value) {
          const skillsHidden = document.getElementById('brief-skills');
          if (skillsHidden) skillsHidden.value = result.skills;
        }
        extractBtn.textContent = '✓ Done';
      }
    } catch (err) {
      extractBtn.textContent = 'Extract text';
      extractBtn.disabled = false;
      setWizardStatus(String(err), true);
    }
  });
}

const briefingFields = {
  full_name: document.getElementById('brief-full-name'),
  current_role: document.getElementById('brief-current-role'),
  experience_years: document.getElementById('brief-experience-years'),
  location: document.getElementById('brief-location'),
  work_mode: document.getElementById('brief-work-mode'),
  resume_filename: document.getElementById('brief-resume-filename'),
  resume_text: document.getElementById('brief-resume-text'),
  skills: document.getElementById('brief-skills'),
  strongest_skill: document.getElementById('brief-strongest-skill'),
  recent_company: document.getElementById('brief-recent-company'),
  work_duration: document.getElementById('brief-work-duration'),
  reason_for_change: document.getElementById('brief-reason-for-change'),
  salary_expectations: document.getElementById('brief-salary-expectations'),
  strongest_skill_example: document.getElementById('brief-strongest-example'),
  experience_highlights: document.getElementById('brief-experience-highlights'),
  project_name: document.getElementById('brief-project-name'),
  project_technologies: document.getElementById('brief-project-technologies'),
  project_summary: document.getElementById('brief-project-summary'),
  project_contribution: document.getElementById('brief-project-contribution'),
  technical_weak_areas: document.getElementById('brief-technical-weak-areas'),
  english_fluency_level: document.getElementById('brief-english-fluency-level'),
  interview_anxiety_level: document.getElementById('brief-interview-anxiety-level'),
  weakness_story: document.getElementById('brief-weakness-story'),
  improvement_actions: document.getElementById('brief-improvement-actions'),
  target_role: document.getElementById('brief-target-role'),
  company_name: document.getElementById('brief-company-name'),
  meeting_source: document.getElementById('brief-meeting-source'),
  meeting_window_name: document.getElementById('brief-meeting-window-name'),
  company_values: document.getElementById('brief-company-values'),
  meeting_capture_mode: document.getElementById('brief-meeting-capture-mode'),
  camera_layout_preference: document.getElementById('brief-camera-layout-preference'),
  industry: document.getElementById('brief-industry'),
  company_type: document.getElementById('brief-company-type'),
  interview_difficulty: document.getElementById('brief-interview-difficulty'),
  expected_questions: document.getElementById('brief-expected-questions'),
  answer_style: document.getElementById('brief-answer-style'),
  live_constraints: document.getElementById('brief-live-constraints'),
  use_microphone: document.getElementById('brief-use-microphone'),
};

function setWizardStatus(message, isError = false) {
  if (wizardStatus === null) {
    return;
  }
  wizardStatus.textContent = message;
  wizardStatus.classList.toggle('error', isError);
}

function buildWizardStepper() {
  if (wizardStepper === null) {
    return;
  }
  wizardStepper.innerHTML = '';
  wizardModel.forEach((step, index) => {
    const row = document.createElement('article');
    row.className = `wizard-step-indicator${index === currentWizardStep ? ' active' : ''}`;
    row.innerHTML = `<strong>Step ${index + 1}: ${step.title}</strong><span>${step.description}</span>`;
    row.addEventListener('click', () => {
      currentWizardStep = index;
      renderWizardStep();
    });
    wizardStepper.appendChild(row);
  });
}

function renderWizardStep() {
  wizardSteps.forEach((step, index) => {
    step.classList.toggle('hidden', index !== currentWizardStep);
  });
  if (wizardTitle !== null) {
    wizardTitle.textContent = wizardModel[currentWizardStep].title;
  }
  if (wizardStepLabel !== null) {
    wizardStepLabel.textContent = `Step ${currentWizardStep + 1} of ${wizardModel.length}`;
  }
  if (wizardBackButton !== null) {
    wizardBackButton.disabled = currentWizardStep === 0;
  }
  if (wizardNextButton !== null) {
    wizardNextButton.disabled = currentWizardStep === wizardModel.length - 1;
  }
  buildWizardStepper();
}

function collectBriefingPayload() {
  const payload = {};
  Object.entries(briefingFields).forEach(([key, element]) => {
    if (element !== null) {
      payload[key] = element.type === 'checkbox' ? element.checked : element.value;
    }
  });
  return payload;
}

function resumeQuickStartReady(payload) {
  return String(payload.resume_text || '').trim().length > 0 || String(payload.resume_filename || '').trim().length > 0;
}

function fillBriefingForm(payload) {
  Object.entries(briefingFields).forEach(([key, element]) => {
    if (element !== null && payload[key] !== undefined) {
      if (element.type === 'checkbox') {
        element.checked = Boolean(payload[key]);
      } else {
        element.value = payload[key];
      }
    }
  });
  renderWizardAlignment(payload);
}

function renderMicrophoneMode(snapshot) {
  if (microphoneMode === null) {
    return;
  }
  microphoneMode.textContent = snapshot.microphone_enabled ? 'Live microphone' : 'Scripted preview';
}

function summarizeBriefingModel(payload = collectBriefingPayload()) {
  const fullName = String(payload.full_name || '').trim();
  const currentRole = String(payload.current_role || '').trim();
  const targetRole = String(payload.target_role || '').trim();
  const strongestSkill = String(payload.strongest_skill || '').trim();
  const strongestExample = String(payload.strongest_skill_example || '').trim();
  const answerStyle = String(payload.answer_style || '').trim();
  const meetingSource = String(payload.meeting_source || 'Manual / generic interview').trim() || 'Manual / generic interview';
  const meetingCaptureMode = String(payload.meeting_capture_mode || 'Companion workspace with live mic capture').trim() || 'Companion workspace with live mic capture';

  const identitySummary = fullName || currentRole || targetRole
    ? `${fullName || 'Candidate'} · ${currentRole || 'Professional'}${targetRole ? ` -> ${targetRole}` : ''}`
    : 'Waiting for profile context';
  const proofSummary = strongestSkill
    ? `${strongestSkill}${strongestExample ? ` backed by ${strongestExample}` : ''}`
    : 'Add a strongest skill and one proof example';

  return {
    identitySummary,
    proofSummary,
    meetingSummary: `${meetingSource} · ${meetingCaptureMode}`,
    toneSummary: answerStyle || 'Simple, calm, credible',
  };
}

function renderWizardAlignment(payload = collectBriefingPayload()) {
  const model = summarizeBriefingModel(payload);
  if (wizardAlignmentRole !== null) {
    wizardAlignmentRole.textContent = model.identitySummary;
  }
  if (wizardAlignmentProof !== null) {
    wizardAlignmentProof.textContent = model.proofSummary;
  }
  if (wizardAlignmentMeeting !== null) {
    wizardAlignmentMeeting.textContent = model.meetingSummary;
  }
  if (wizardAlignmentTone !== null) {
    wizardAlignmentTone.textContent = model.toneSummary;
  }
}

function renderSessionAlignment(payload) {
  const model = summarizeBriefingModel();
  if (alignmentIdentity !== null) {
    alignmentIdentity.textContent = `${payload.snapshot.profile_name} · ${payload.snapshot.role_title} at ${payload.snapshot.company_name}`;
  }
  if (alignmentProof !== null) {
    alignmentProof.textContent = model.proofSummary;
  }
  if (alignmentMeeting !== null) {
    alignmentMeeting.textContent = `${payload.snapshot.meeting_source || 'Manual / generic interview'} · ${payload.snapshot.meeting_capture_mode || 'Companion workspace with live mic capture'}`;
  }
  if (alignmentTone !== null) {
    alignmentTone.textContent = model.toneSummary;
  }
}

function applyMicrophoneStatus(statusPayload) {
  const microphoneToggle = briefingFields.use_microphone;
  if (microphoneToggle === null || !statusPayload) {
    return;
  }

  const canCapture = Boolean(statusPayload.can_capture);
  const message = statusPayload.message || '';
  microphoneToggle.disabled = !canCapture;
  if (!canCapture) {
    microphoneToggle.checked = false;
  } else if (!microphoneToggle.dataset.userTouched) {
    microphoneToggle.checked = true;
  }

  if (microphoneBanner !== null) {
    microphoneBanner.textContent = message;
    microphoneBanner.classList.toggle('hidden', canCapture && !message);
    microphoneBanner.classList.toggle('info-banner--warning', !canCapture);
    microphoneBanner.classList.toggle('info-banner--success', canCapture);
  }
}

async function loadBriefing() {
  try {
    const response = await fetch('/api/briefing');
    const payload = await parseApiPayload(response, 'Failed to load briefing.');
    if (!response.ok) {
      throw new Error(payload.error || `Request failed: ${response.status}`);
    }
    fillBriefingForm(payload);
    applyMicrophoneStatus(payload.microphone || null);
    if (payload.profile_path) {
      setWizardStatus(`Saved briefing loaded from ${payload.profile_path}.`);
    }
  } catch (error) {
    setWizardStatus(String(error), true);
  }
}

function setBriefingButtonsBusy(isBusy) {
  [wizardSaveButton, wizardQuickStartButton, wizardBackButton, wizardNextButton].forEach((button) => {
    if (button !== null) {
      button.disabled = isBusy;
    }
  });
}

async function ensureCanGoLive() {
  const response = await fetch('/api/system/preflight', { headers: { Accept: 'application/json' } });
  const payload = await parseApiPayload(response, 'Preflight check failed.');
  if (payload.can_go_live) {
    return payload;
  }
  const blockers = (payload.checks || [])
    .filter((check) => !check.ok && ['license', 'microphone', 'ai'].includes(check.id))
    .map((check) => check.hint || check.label)
    .filter(Boolean);
  const message = blockers.length
    ? `Complete setup first: ${blockers.join(' ')}`
    : 'Complete activation, audio, and AI setup before going live.';
  throw new Error(message);
}

async function saveBriefing(sessionMode = 'progressive') {
  const briefingPayload = collectBriefingPayload();
  if (sessionMode === 'resume_only' && !resumeQuickStartReady(briefingPayload)) {
    setWizardStatus('Resume Quick Start needs an uploaded or pasted resume first.', true);
    return;
  }

  try {
    await ensureCanGoLive();
  } catch (error) {
    setWizardStatus(String(error.message || error), true);
    return;
  }

  const activeButton = sessionMode === 'resume_only' ? wizardQuickStartButton : wizardSaveButton;
  const originalLabel = activeButton ? activeButton.textContent : '';

  try {
    setBriefingButtonsBusy(true);
    if (activeButton !== null) {
      activeButton.textContent = sessionMode === 'resume_only' ? 'Starting…' : 'Creating…';
    }

    const response = await fetch('/api/briefing', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...briefingPayload,
        session_mode: sessionMode,
      }),
    });
    const payload = await parseApiPayload(response, 'Failed to create session.');
    if (!response.ok) {
      if (Array.isArray(payload.issues) && payload.issues.length > 0) {
        throw new Error(`Complete these fields: ${payload.issues.join(' | ')}`);
      }
      throw new Error(payload.error || `Request failed: ${response.status}`);
    }
    fillBriefingForm(payload.briefing || {});
    if (payload.session_id) {
      currentSessionId = payload.session_id;
      sessionInput.value = payload.session_id;
      applyMicrophoneStatus(payload.microphone || payload.session?.microphone || null);
      if (payload.session) {
        renderSnapshot(payload.session);
      }
      closeEventStream();
      stopPolling();
      startEventStream();
      statusLine.textContent = `✅ Session ready: ${payload.session_id} — ${payload.company_name || 'Company'} · ${payload.role_name || 'Role'}`;
      statusLine.classList.remove('error');
      window.showToast?.('✅ Session created successfully. Overlay and dashboard are live.', 'success');
      loadRecentSessions();
      const modeLabel = payload.profile_readiness === 'session_ready'
        ? 'Resume-backed instant session is live.'
        : 'Full profile session is live.';
      const deferred = Array.isArray(payload.deferred_issues) && payload.deferred_issues.length > 0
        ? ` Complete later: ${payload.deferred_issues.slice(0, 3).join(' | ')}.`
        : '';
      setWizardStatus(`${modeLabel} Profile ready at ${payload.profile_path}. Auto-connected to session ${payload.session_id}.${deferred}`);
      return;
    }
    setWizardStatus(`Briefing saved. Profile ready at ${payload.profile_path}.`);
  } catch (error) {
    const message = String(error?.message || error || 'Request failed');
    if (message === 'Failed to fetch' || error?.name === 'TypeError') {
      setWizardStatus(
        'Dashboard connection lost while creating the session. Keep Career Copilot Premium open, wait a few seconds, then click Create session again.',
        true,
      );
      return;
    }
    setWizardStatus(message, true);
  } finally {
    setBriefingButtonsBusy(false);
    if (activeButton !== null) {
      activeButton.textContent = originalLabel;
    }
  }
}

async function parseApiPayload(response, fallbackMessage) {
  const contentType = String(response.headers.get('content-type') || '').toLowerCase();
  const rawBody = await response.text();

  if (!rawBody.trim()) {
    return {};
  }

  if (contentType.includes('application/json')) {
    try {
      return JSON.parse(rawBody);
    } catch {
      throw new Error(`${fallbackMessage} Invalid JSON response from server.`);
    }
  }

  const compact = rawBody.replace(/\s+/g, ' ').trim().toLowerCase();
  if (compact.startsWith('<!doctype') || compact.startsWith('<html') || compact.startsWith('<')) {
    throw new Error(`${fallbackMessage} Server returned HTML instead of JSON.`);
  }

  try {
    return JSON.parse(rawBody);
  } catch {
    throw new Error(`${fallbackMessage} Unexpected response format from server.`);
  }
}

function promptStorageKey(sessionId) {
  return `career-copilot:workspace-prompts:${sessionId || 'global'}`;
}

function activePromptSessionId() {
  return currentSessionId || sessionInput.value.trim() || 'global';
}

function setStatusPill(element, label, tone) {
  element.textContent = label;
  element.className = `status-pill status-pill--${tone}`;
}

function setPromptStatus(message, isError = false) {
  promptStatus.textContent = message;
  promptStatus.classList.toggle('error', isError);
}

function loadPromptDrafts(serverPrompts = null) {
  if (serverPrompts && (serverPrompts.persistent || serverPrompts.live)) {
    persistentPrompt.value = serverPrompts.persistent || '';
    livePrompt.value = serverPrompts.live || '';
    setPromptStatus('Loaded saved operator brief from the live session.');
    localStorage.setItem(promptStorageKey(activePromptSessionId()), JSON.stringify({
      persistent: persistentPrompt.value,
      live: livePrompt.value,
      savedAt: new Date().toLocaleString(),
    }));
    return;
  }

  let payload = {};
  try {
    payload = JSON.parse(localStorage.getItem(promptStorageKey(activePromptSessionId())) || '{}');
  } catch {
    payload = {};
  }

  persistentPrompt.value = payload.persistent || '';
  livePrompt.value = payload.live || '';
  if (payload.savedAt) {
    setPromptStatus(`Saved locally for this session at ${payload.savedAt}.`);
  } else {
    setPromptStatus('No operator brief saved yet.');
  }
}

async function savePromptDrafts() {
  const payload = {
    persistent: persistentPrompt.value.trim(),
    live: livePrompt.value.trim(),
    savedAt: new Date().toLocaleString(),
  };
  localStorage.setItem(promptStorageKey(activePromptSessionId()), JSON.stringify(payload));
  if (!currentSessionId) {
    setPromptStatus(`Saved locally for session ${activePromptSessionId()}.`);
    return;
  }

  try {
    const response = await fetch(`/api/session/${currentSessionId}/prompts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        persistent_prompt: payload.persistent,
        live_prompt: payload.live,
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || `Request failed: ${response.status}`);
    }
    renderSnapshot(result);
    setPromptStatus(`Saved locally and synced to session ${currentSessionId}.`);
  } catch (error) {
    setPromptStatus(String(error), true);
  }
}

function clearPromptDrafts() {
  localStorage.removeItem(promptStorageKey(activePromptSessionId()));
  persistentPrompt.value = '';
  livePrompt.value = '';
  setPromptStatus('Operator brief cleared for this session.');
}

function stopPolling() {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

function closeEventStream() {
  if (eventSource !== null) {
    eventSource.close();
    eventSource = null;
  }
}

function startPollingFallback() {
  stopPolling();
  refreshTimer = window.setInterval(fetchSnapshot, 8000);
}

function startEventStream() {
  if (!currentSessionId || typeof EventSource === 'undefined') {
    startPollingFallback();
    return;
  }

  closeEventStream();
  stopPolling();
  eventSource = new EventSource(`/api/session/${currentSessionId}/events`);
  eventSource.addEventListener('snapshot', (event) => {
    const payload = JSON.parse(event.data);
    renderSnapshot(payload);
    statusLine.textContent = `Connected to ${payload.snapshot.session_id}`;
    statusLine.classList.remove('error');
  });
  eventSource.addEventListener('error', () => {
    closeEventStream();
    startPollingFallback();
  });
}

function buildReadinessModel(payload) {
  if (payload.readiness) {
    return {
      label: payload.readiness.label,
      title: payload.readiness.title,
      hint: payload.readiness.hint,
      tone: payload.readiness.tone,
      callLabel: payload.readiness.call_label,
      callTone: payload.readiness.call_tone,
      workspaceMode: payload.readiness.workspace_mode,
    };
  }

  const overlayState = payload.overlay.status || 'idle';
  const workerState = payload.snapshot.worker_status || 'unknown';
  const armed = Boolean(payload.snapshot.session_armed);

  if (overlayState === 'answer_ready') {
    return {
      label: 'Ready',
      title: 'Reply ready',
      hint: 'AI has already drafted a primary reply and fallback options for the latest interviewer prompt.',
      tone: 'ready',
      callLabel: 'Question captured',
      callTone: 'ready',
      workspaceMode: 'answer_ready',
    };
  }

  if (overlayState === 'listening') {
    return {
      label: 'Listening',
      title: 'Listening live',
      hint: 'Microphone capture is active. Keep speaking naturally while the assistant waits for the next interviewer prompt.',
      tone: 'listening',
      callLabel: 'Live capture',
      callTone: 'listening',
      workspaceMode: 'listening',
    };
  }

  if (armed || workerState === 'running') {
    return {
      label: 'Armed',
      title: 'Waiting for the next question',
      hint: 'Your session is prepared. The assistant is ready to switch into listening and answer generation as soon as the interviewer speaks.',
      tone: 'armed',
      callLabel: 'Waiting for caller',
      callTone: 'armed',
      workspaceMode: 'armed',
    };
  }

  return {
    label: 'Idle',
    title: 'Standby',
    hint: 'Load a session and use the live controls to prepare for the next question.',
    tone: 'neutral',
    callLabel: 'Standby',
    callTone: 'standby',
    workspaceMode: 'standby',
  };
}

function sanitizeDisplayText(value, fallback = '') {
  const text = String(value || '')
    .replace(/\uFFFD/g, ' ')
    .replace(/[^\x09\x0A\x20-\x7E\u00A0-\uFFFF]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (!text) {
    return fallback;
  }
  const letters = (text.match(/[A-Za-z]/g) || []).length;
  if (letters < Math.max(2, Math.floor(text.length * 0.12))) {
    return fallback;
  }
  return text.length > 500 ? `${text.slice(0, 497)}...` : text;
}

function renderTimeline(payload) {
  const items = [
    {
      label: 'Session readiness',
      value: payload.snapshot.session_armed
        ? 'Strategy pack loaded and interview mode is armed for live assistance.'
        : 'The session is visible, but the live assist stack is not armed yet.',
    },
    {
      label: 'Worker state',
      value: `Worker is currently ${payload.snapshot.worker_status || 'unknown'}.`,
    },
    {
      label: 'Model status',
      value: payload.overlay.provider_status || 'Provider connection has not been reported yet.',
    },
  ];

  const detectedPrompt = sanitizeDisplayText(payload.overlay.headline, '');
  if (detectedPrompt) {
    items.unshift({
      label: 'Detected prompt',
      value: detectedPrompt,
    });
  }

  timelineList.innerHTML = '';
  items.forEach((item) => {
    const row = document.createElement('article');
    row.className = 'timeline-item';
    row.innerHTML = `<strong>${item.label}</strong><span>${item.value}</span>`;
    timelineList.appendChild(row);
  });
}

function renderAlternatives(alternatives) {
  alternativesList.innerHTML = '';
  if (!alternatives.length) {
    const empty = document.createElement('article');
    empty.className = 'alternative-item';
    empty.innerHTML = '<strong>No fallback yet</strong><span>Alternative replies will appear here when the assistant has enough context.</span>';
    alternativesList.appendChild(empty);
    return;
  }

  alternatives.forEach((alternative, index) => {
    const row = document.createElement('article');
    row.className = 'alternative-item';
    row.innerHTML = `<strong>Option ${index + 1}</strong><span>${alternative}</span>`;
    alternativesList.appendChild(row);
  });
}

function renderNotificationHistory(notifications) {
  if (historyList === null || historyStatus === null) {
    return;
  }

  const items = Array.isArray(notifications) ? notifications : [];
  const latestWarning = items.find((item) => String(item.level || '').toLowerCase() === 'warning');
  const latestError = items.find((item) => String(item.level || '').toLowerCase() === 'error');

  if (latestError) {
    setStatusPill(historyStatus, 'Needs review', 'danger');
  } else if (latestWarning) {
    setStatusPill(historyStatus, 'Watch fallback', 'warning');
  } else if (items.length) {
    setStatusPill(historyStatus, 'Healthy', 'ready');
  } else {
    setStatusPill(historyStatus, 'No alerts', 'neutral');
  }

  historyList.innerHTML = '';
  if (!items.length) {
    const empty = document.createElement('article');
    empty.className = 'history-item history-item--empty';
    empty.innerHTML = '<strong>No activity yet</strong><span>Connect a session to inspect its latest safety and workflow events.</span>';
    historyList.appendChild(empty);
    return;
  }

  items.slice().reverse().forEach((item) => {
    const level = String(item.level || 'info').toLowerCase();
    const row = document.createElement('article');
    row.className = `history-item history-item--${level}`;
    row.innerHTML = `
      <div class="history-item__header">
        <strong>${item.title || 'Session event'}</strong>
        <span>${item.created_at || ''}</span>
      </div>
      <p>${item.message || ''}</p>
    `;
    historyList.appendChild(row);
  });
}

async function queueSessionAction(actionId) {
  const response = await fetch(`/api/session/${currentSessionId}/actions/${actionId}`, {
    method: 'POST',
  });
  const result = await response.json();
  if (!response.ok) {
    statusLine.textContent = result.error || `Action failed: ${response.status}`;
    statusLine.classList.add('error');
    return false;
  }
  statusLine.textContent = `Queued ${result.queued_action}`;
  statusLine.classList.remove('error');
  window.setTimeout(() => {
    void fetchSnapshot();
  }, 1200);
  return true;
}

function shouldIgnoreWorkspaceShortcut(element) {
  if (!(element instanceof HTMLElement)) {
    return false;
  }
  const tagName = element.tagName.toLowerCase();
  return element.isContentEditable || tagName === 'input' || tagName === 'textarea' || tagName === 'select';
}

async function startInterview() {
  if (startInterviewButton === null) {
    return;
  }
  const originalLabel = startInterviewButton.textContent;
  try {
    startInterviewButton.disabled = true;
    startInterviewButton.textContent = 'Starting…';
    statusLine.textContent = 'Creating session from your saved profile…';
    statusLine.classList.remove('error');

    const response = await fetch('/api/session/quick-start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ use_microphone: true }),
    });
    const payload = await parseApiPayload(response, 'Could not start interview session.');
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || `Request failed: ${response.status}`);
    }

    currentSessionId = payload.session_id || '';
    if (sessionInput !== null) {
      sessionInput.value = currentSessionId;
    }
    if (payload.session) {
      renderSnapshot(payload.session);
    }
    closeEventStream();
    stopPolling();
    startEventStream();
    loadRecentSessions();

      statusLine.textContent =
      payload.hint ||
      `✅ Session ready: ${currentSessionId}. Press F2 or click Listen in the overlay.`;
    statusLine.classList.remove('error');
    window.showToast?.(`✅ Interview session live — ${payload.company_name || 'Company'} · ${payload.role_name || 'Role'}`, 'success');
    setActiveSection('live-dock');
  } catch (error) {
    statusLine.textContent = String(error.message || error);
    statusLine.classList.add('error');
    window.showToast?.(String(error.message || error), 'error');
  } finally {
    startInterviewButton.disabled = false;
    startInterviewButton.textContent = originalLabel;
  }
}

async function loadPortableStatus() {
  const hint = document.getElementById('bridge-lan-hint');
  try {
    const response = await fetch('/api/portable/status');
    const payload = await response.json();
    if (!response.ok || !payload.portable_mode) {
      return;
    }
    if (hint && payload.all_data_in_project_folder) {
      hint.textContent = `Portable USB mode — all sessions and .env stay in this app folder. Mobile bridge on same Wi‑Fi.`;
    }
  } catch {
    // ignore
  }
}

async function loadRecentSessions() {
  try {
    const response = await fetch('/api/sessions/recent', {
      headers: {
        Accept: 'application/json',
      },
    });
    const rawBody = await response.text();
    let payload = {};
    if (rawBody) {
      try {
        payload = JSON.parse(rawBody);
      } catch {
        throw new Error(`Unexpected server response (${response.status}).`);
      }
    }
    if (!response.ok) {
      throw new Error(payload.error || `Request failed: ${response.status}`);
    }
    renderRecentSessions(payload.sessions || []);
  } catch (error) {
    recentSessions.innerHTML = `<p class="recent-empty error">${String(error)}</p>`;
  }
}

async function createPairingCode() {
  const modal = document.getElementById('pairing-modal');
  const qrWrap = document.getElementById('pairing-qr-wrap');
  const digitsEl = document.getElementById('pairing-digits');
  const expiryEl = document.getElementById('pairing-expiry');
  const copyBtn = document.getElementById('pairing-copy-btn');
  const refreshBtn = document.getElementById('pairing-refresh-btn');
  const closeBtn = document.getElementById('pairing-modal-close');

  // Show modal
  if (modal) {
    modal.classList.remove('hidden');
    if (qrWrap) qrWrap.innerHTML = '<div class="pairing-qr-loading">Generating code…</div>';
    renderPairingDigits(digitsEl, '------', true);
    if (expiryEl) expiryEl.textContent = '';
    if (copyBtn) copyBtn.disabled = true;
  }

  if (linkDeviceButton) {
    linkDeviceButton.disabled = true;
    linkDeviceButton.textContent = 'Generating…';
  }

  try {
    const response = await fetch('/api/pairing/create', { method: 'POST' });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || `Request failed: ${response.status}`);
    }

    const code = String(payload.pairing_code || '').trim();
    const expiresSeconds = Number(payload.expires_in_seconds || 180);
    if (!code) throw new Error('Pairing code was not returned by the service.');

    // Update modal with code
    renderPairingDigits(digitsEl, code);
    if (expiryEl) {
      const mins = Math.max(1, Math.round(expiresSeconds / 60));
      expiryEl.textContent = `Expires in ${mins} minute${mins !== 1 ? 's' : ''}`;
    }

    // Load QR as either PNG or inline SVG so the Link Device flow always shows a scannable visual.
    if (qrWrap) {
      qrWrap.innerHTML = '<div class="pairing-qr-loading">Rendering QR…</div>';
      const qrResponse = await fetch(`/api/pairing/qr/${code}`, { cache: 'no-store' });
      if (!qrResponse.ok) {
        throw new Error(`QR request failed: ${qrResponse.status}`);
      }

      const qrType = String(qrResponse.headers.get('content-type') || '').toLowerCase();
      qrWrap.innerHTML = '';

      if (qrType.includes('image/svg')) {
        qrWrap.innerHTML = await qrResponse.text();
      } else {
        const qrBlob = await qrResponse.blob();
        const img = document.createElement('img');
        img.src = URL.createObjectURL(qrBlob);
        img.alt = `QR code for pairing code ${code}`;
        img.className = 'pairing-qr-img';
        img.onload = () => URL.revokeObjectURL(img.src);
        img.onerror = () => {
          qrWrap.innerHTML = `<div class="pairing-qr-fallback">QR image could not load. Use code <strong>${code}</strong>.</div>`;
        };
        qrWrap.appendChild(img);
      }
    }

    // Copy button
    if (copyBtn) {
      copyBtn.disabled = false;
      copyBtn.onclick = async () => {
        try {
          await navigator.clipboard.writeText(code);
          copyBtn.textContent = '✓ Copied';
          setTimeout(() => { copyBtn.textContent = '📋 Copy code'; }, 2000);
        } catch {
          copyBtn.textContent = code;
        }
      };
    }

    // Update pairing line below session dock
    if (pairingCodeLine) {
      pairingCodeLine.textContent = `Active pairing code: ${code} — valid ${Math.max(1, Math.round(expiresSeconds / 60))} min`;
    }
    statusLine.textContent = `Pairing code ready: ${code}. Scan QR or enter in mobile app.`;
    statusLine.classList.remove('error');

  } catch (error) {
    if (qrWrap) qrWrap.innerHTML = `<div class="pairing-qr-error">${String(error)}</div>`;
    renderPairingDigits(digitsEl, 'ERROR', true);
    statusLine.textContent = String(error);
    statusLine.classList.add('error');
  } finally {
    if (linkDeviceButton) {
      linkDeviceButton.disabled = false;
      linkDeviceButton.textContent = 'Link Device';
    }
  }

  // Wire close and refresh
  if (closeBtn) {
    closeBtn.onclick = () => modal && modal.classList.add('hidden');
  }
  if (refreshBtn) {
    refreshBtn.onclick = () => createPairingCode();
  }
  if (modal) {
    modal.onclick = (e) => {
      if (e.target === modal) modal.classList.add('hidden');
    };
  }
}

function renderPairingDigits(element, value, isPlaceholder = false) {
  if (element === null) {
    return;
  }

  const digits = String(value || '').trim();
  if (!digits) {
    element.textContent = '';
    return;
  }

  element.classList.toggle('pairing-digits--placeholder', isPlaceholder);
  element.innerHTML = digits
    .split('')
    .map((character, index) => `<span class="pairing-digit pairing-digit--${index % 2 === 0 ? 'cool' : 'warm'}">${character}</span>`)
    .join('');
}

function formatSessionStatusBadge(status) {
  const normalized = String(status || 'stopped').toLowerCase();
  if (normalized === 'running') {
    return '<span class="session-status-badge session-status-badge--running">● Running</span>';
  }
  if (normalized === 'new') {
    return '<span class="session-status-badge session-status-badge--new">● New</span>';
  }
  return '<span class="session-status-badge session-status-badge--stopped">● Stopped</span>';
}

async function deleteOldSessions() {
  const button = document.getElementById('delete-old-sessions-button');
  const originalLabel = button ? button.textContent : '';
  try {
    if (button) {
      button.disabled = true;
      button.textContent = 'Deleting…';
    }
    const response = await fetch('/api/sessions/cleanup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hours_old: 24 }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || `Request failed: ${response.status}`);
    }
    statusLine.textContent = payload.message || 'Old sessions deleted.';
    statusLine.classList.remove('error');
    window.showToast?.(payload.message || 'Old sessions deleted.', 'success');
    loadRecentSessions();
  } catch (error) {
    statusLine.textContent = String(error.message || error);
    statusLine.classList.add('error');
    window.showToast?.(String(error.message || error), 'error');
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  }
}

function renderRecentSessions(sessions) {
  if (!sessions.length) {
    recentSessions.innerHTML = `
      <div class="recent-empty-state">
        <div class="recent-empty-icon" aria-hidden="true">
          <svg viewBox="0 0 64 64" role="presentation" focusable="false">
            <circle cx="32" cy="32" r="26"></circle>
            <path d="M32 21v22M21 32h22"></path>
          </svg>
        </div>
        <h4>No saved sessions yet</h4>
        <p>Create your first session to start practicing</p>
        <button id="create-first-session-button" class="empty-state-button" type="button">
          <span class="button-icon" aria-hidden="true">
            <svg viewBox="0 0 16 16" role="presentation" focusable="false">
              <path d="M8 3v10M3 8h10"></path>
            </svg>
          </span>
          Create First Session
        </button>
      </div>
    `;
    recentSessions.querySelector('#create-first-session-button')?.addEventListener('click', () => {
      applyGeneratedSessionId();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    return;
  }

  recentSessions.innerHTML = '';
  sessions.forEach((session, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'recent-session-button';
    button.innerHTML = `
      <span class="recent-session-title">${session.profile_name} · ${session.company_name}</span>
      <span class="recent-session-meta">${session.role_title} · ${session.meeting_source || 'Manual / generic interview'} ${formatSessionStatusBadge(session.session_status || session.worker_status)}</span>
    `;
    button.addEventListener('click', async () => {
      sessionInput.value = session.session_id;
      currentSessionId = session.session_id;
      closeEventStream();
      stopPolling();
      const connected = await fetchSnapshot();
      if (connected) {
        startEventStream();
      }
    });
    recentSessions.appendChild(button);

    if (index === 0 && !currentSessionId && !sessionInput.value.trim()) {
      sessionInput.value = session.session_id;
      statusLine.textContent = `Demo session ready: ${session.session_id}`;
      statusLine.classList.remove('error');
      loadPromptDrafts();
    }
  });
}

async function fetchSnapshot() {
  if (!currentSessionId) {
    return false;
  }
  try {
    const response = await fetch(`/api/session/${currentSessionId}`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || `Request failed: ${response.status}`);
    }
    renderSnapshot(payload);
    statusLine.textContent = `Connected to ${payload.snapshot.session_id}`;
    statusLine.classList.remove('error');
    return true;
  } catch (error) {
    statusLine.textContent = String(error);
    statusLine.classList.add('error');
    return false;
  }
}

function renderSnapshot(payload) {
  snapshotCard.classList.remove('hidden');
  updateSectionNavMeta();
  const readiness = buildReadinessModel(payload);
  applyMicrophoneStatus(payload.microphone || null);
  const meetingSource = payload.snapshot.meeting_source || 'Manual / generic interview';
  const meetingCaptureMode = payload.snapshot.meeting_capture_mode || 'Companion workspace with live mic capture';
  const meetingWindowName = payload.snapshot.meeting_window_name || `${payload.snapshot.company_name} live interview`;
  const cameraLayoutPreference = payload.snapshot.camera_layout_preference || 'Keep Career Copilot beside the meeting window';

  companyName.textContent = payload.snapshot.company_name;
  roleTitle.textContent = payload.snapshot.role_title;
  callerName.textContent = `${meetingSource} · ${meetingWindowName}`;
  callerStageCopy.textContent = `Career Copilot is armed for ${meetingSource}. Keep the real caller video in ${meetingSource}, and use this workspace to watch prompts, capture the latest question, and deliver live answer support for ${payload.snapshot.profile_name}'s ${payload.snapshot.role_title} interview at ${payload.snapshot.company_name}.`;
  meetingSourceChip.textContent = meetingSource;
  meetingCaptureChip.textContent = meetingCaptureMode;
  cameraLayoutCopy.textContent = cameraLayoutPreference;
  companyChip.textContent = payload.snapshot.company_name;
  roleChip.textContent = payload.snapshot.role_title;
  candidateChip.textContent = payload.snapshot.profile_name;
  turnCount.textContent = `${payload.snapshot.turn_count || 0} turns`;
  setStatusPill(overlayStatus, readiness.label, readiness.tone);
  setStatusPill(callState, readiness.callLabel, readiness.callTone);
  readinessTitle.textContent = readiness.title;
  readinessHint.textContent = readiness.hint;
  headline.textContent = sanitizeDisplayText(
    payload.overlay.headline,
    'Waiting for the next interviewer prompt.',
  );
  transcriptSummary.textContent = payload.overlay.status === 'answer_ready'
    ? 'The interviewer prompt above has been detected and converted into a reply-ready state.'
    : 'This panel will highlight the latest question and readiness signal as soon as the conversation moves.';
  body.textContent = sanitizeDisplayText(
    payload.overlay.body,
    'Primary reply draft will appear here when AI is ready.',
  );
  confidenceScore.textContent = `${payload.overlay.confidence_score}%`;
  workerStatus.textContent = payload.snapshot.worker_status;
  updatedAt.textContent = payload.snapshot.updated_at || '-';
  updateProviderIndicator(payload.overlay.provider_status || 'Not connected');
  updateWorkspaceModeIndicator(readiness.workspaceMode);
  renderMicrophoneMode(payload.snapshot);
  renderSessionAlignment(payload);

  renderTimeline(payload);
  renderAlternatives(payload.overlay.alternatives || []);
  renderNotificationHistory(payload.snapshot.notifications || []);
  loadPromptDrafts(payload.prompts || null);

  actionGrid.innerHTML = '';
  payload.overlay.actions.forEach((action) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'action-button';
    button.textContent = action.label;
    if (action.action_id === 'listen' || action.action_id === 'toggle') {
      button.dataset.shortcut = 'F2';
    }
    button.addEventListener('click', async () => {
      await queueSessionAction(action.action_id);
    });
    actionGrid.appendChild(button);
  });
}

if (savePromptsButton !== null) {
  savePromptsButton.addEventListener('click', async () => {
    await savePromptDrafts();
  });
}

if (clearPromptsButton !== null) {
  clearPromptsButton.addEventListener('click', () => {
    clearPromptDrafts();
  });
}

if (wizardBackButton !== null) {
  wizardBackButton.addEventListener('click', () => {
    currentWizardStep = Math.max(0, currentWizardStep - 1);
    renderWizardStep();
  });
}

if (wizardNextButton !== null) {
  wizardNextButton.addEventListener('click', () => {
    currentWizardStep = Math.min(wizardModel.length - 1, currentWizardStep + 1);
    renderWizardStep();
  });
}

if (wizardSaveButton !== null) {
  wizardSaveButton.addEventListener('click', async () => {
    await saveBriefing();
  });
}

if (wizardQuickStartButton !== null) {
  wizardQuickStartButton.addEventListener('click', async () => {
    await saveBriefing('resume_only');
  });
}

promptChips.forEach((chip) => {
  chip.addEventListener('click', () => {
    const target = chip.dataset.target === 'live' ? livePrompt : persistentPrompt;
    const value = chip.dataset.value || '';
    target.value = target.value.trim() ? `${target.value.trim()} ${value}` : value;
  });
});

Object.values(briefingFields).forEach((element) => {
  if (element === null) {
    return;
  }
  const eventName = element.tagName === 'SELECT' || element.type === 'checkbox' ? 'change' : 'input';
  element.addEventListener(eventName, () => {
    if (element === briefingFields.use_microphone) {
      element.dataset.userTouched = '1';
    }
    renderWizardAlignment();
  });
});

connectButton.addEventListener('click', async () => {
  currentSessionId = sessionInput.value.trim();
  if (!currentSessionId) {
    statusLine.textContent = 'Enter a session ID first.';
    statusLine.classList.add('error');
    return;
  }
  closeEventStream();
  stopPolling();
  const connected = await fetchSnapshot();
  if (connected) {
    startEventStream();
  }
});

if (startInterviewButton !== null) {
  startInterviewButton.addEventListener('click', () => {
    startInterview();
  });
}

if (generateSessionButton !== null) {
  generateSessionButton.addEventListener('click', () => {
    applyGeneratedSessionId();
  });
}

if (linkDeviceButton !== null) {
  linkDeviceButton.addEventListener('click', async () => {
    await createPairingCode();
  });
}

if (createFirstSessionButton !== null) {
  createFirstSessionButton.addEventListener('click', () => {
    startInterview();
  });
}

if (sessionInput !== null) {
  sessionInput.addEventListener('keydown', async (event) => {
    if (event.key !== 'Enter') {
      return;
    }
    event.preventDefault();
    connectButton.click();
  });
}

window.addEventListener('beforeunload', () => {
  closeEventStream();
  stopPolling();
});

async function runLiveListen() {
  if (!currentSessionId) {
    statusLine.textContent = 'Connect a live session before using F2.';
    statusLine.classList.add('error');
    return;
  }
  statusLine.textContent = 'Listening to interviewer...';
  statusLine.classList.remove('error');
  try {
    const response = await fetch(`/api/session/${currentSessionId}/listen`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ max_seconds: 12 }),
    });
    const payload = await parseApiPayload(response, 'Live listen failed.');
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || `Request failed: ${response.status}`);
    }
    if (payload.session) {
      renderSnapshot(payload.session);
    }
    statusLine.textContent = 'Answer ready in overlay. Read it in your accent.';
    window.showToast?.('Live answer generated.', 'success');
  } catch (error) {
    statusLine.textContent = String(error.message || error);
    statusLine.classList.add('error');
    window.showToast?.(String(error.message || error), 'error');
  }
}

window.addEventListener('keydown', async (event) => {
  if (event.key !== 'F2' || shouldIgnoreWorkspaceShortcut(document.activeElement)) {
    return;
  }
  event.preventDefault();
  await runLiveListen();
});

renderWizardStep();
initializeSectionNav();
initAllComboboxes();
initResumeBrowse();
loadBriefing();
renderWizardAlignment();
loadPromptDrafts();
updateProviderIndicator('Not connected');
updateWorkspaceModeIndicator('standby');
loadRecentSessions();
loadSystemPreflight();

async function loadSystemPreflight() {
  const list = document.getElementById('preflight-checks');
  const summary = document.getElementById('preflight-summary');
  const hint = document.getElementById('preflight-hint');
  if (!list || !summary) {
    return;
  }
  try {
    const response = await fetch('/api/system/preflight', { headers: { Accept: 'application/json' } });
    const payload = await parseApiPayload(response, 'Preflight check failed.');
    const checks = Array.isArray(payload.checks) ? payload.checks : [];
    list.innerHTML = checks.map((check) => {
      const ok = Boolean(check.ok);
      const statusClass = ok ? 'preflight-check--ok' : 'preflight-check--warn';
      const statusLabel = ok ? 'Ready' : 'Action needed';
      return `<li class="preflight-check ${statusClass}"><strong>${check.label || 'Check'}</strong><span>${statusLabel}</span><p>${check.hint || ''}</p></li>`;
    }).join('');
    if (payload.can_go_live) {
      summary.textContent = 'All required systems are ready. You can start your interview session.';
      if (hint) hint.textContent = 'Press F2 during the call to capture the interviewer and show your answer overlay.';
    } else {
      summary.textContent = 'Some required checks need attention before going live.';
      if (hint) hint.textContent = 'Fix the items marked Action needed, then refresh this page.';
    }
  } catch (error) {
    summary.textContent = 'Could not load system readiness.';
    list.innerHTML = `<li class="preflight-check preflight-check--warn"><strong>Preflight</strong><span>Error</span><p>${String(error.message || error)}</p></li>`;
  }
}

async function loadBridgeLanHint() {
  const hint = document.getElementById('bridge-lan-hint');
  const badge = document.getElementById('mobile-connection-badge');
  if (!hint) {
    return;
  }
  try {
    const response = await fetch('/api/bridge/status');
    const payload = await response.json();
    if (!response.ok || !payload.bridge_url) {
      return;
    }
    const parsed = new URL(payload.bridge_url);
    const host = parsed.hostname;
    const port = parsed.port || '8765';
    hint.textContent = `Mobile: on the same Wi‑Fi, enter ${host} port ${port} in the app (or tap Auto Fix).`;
    if (badge) {
      if (payload.mobile_connected) {
        const sessionSuffix = payload.mobile_session_id ? ` · session ${payload.mobile_session_id}` : '';
        badge.textContent = `📱 Phone connected${sessionSuffix}`;
        badge.classList.add('mobile-connected');
      } else {
        badge.textContent = '📱 Phone: not connected — tap Link Device to pair';
        badge.classList.remove('mobile-connected');
      }
    }
  } catch {
    hint.textContent = 'Mobile: same Wi‑Fi as this PC, then Link Device.';
    if (badge) {
      badge.textContent = '📱 Phone: not connected';
      badge.classList.remove('mobile-connected');
    }
  }
}

document.getElementById('delete-old-sessions-button')?.addEventListener('click', deleteOldSessions);
loadBridgeLanHint();
setInterval(loadBridgeLanHint, 30000);
loadPortableStatus();