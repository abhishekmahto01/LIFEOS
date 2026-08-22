/**
 * ABHISHEK — PORTFOLIO DATA STORE
 * Centralized, structured, easily editable personal data file.
 * Contains truthful metrics, case studies, skills, timeline, and configurations.
 */

export const PORTFOLIO_CONFIG = {
  name: "Abhishek",
  title: "Data Analyst → Aspiring Data Scientist",
  tagline: "Turning messy data into clear decisions.",
  location: "India",
  status: "OPEN TO DATA ANALYST / DATA SCIENTIST OPPORTUNITIES",
  lifeosUrl: "/login", // Local LifeOS route or environment URL
  githubUrl: "https://github.com/abhishekmahto01",
  linkedinUrl: "https://linkedin.com/in/",
  email: "abhishekmahto.work@gmail.com",
};

// 1. HERO TELEMETRY PROFILE
export const HERO_TELEMETRY = {
  experienceYears: "3+",
  projectsCount: "8+",
  dashboardsCount: "4+",
  sqlProficiency: "9/10",
  pythonLevel: "Advanced",
  powerBiLevel: "Advanced",
  postgresLevel: "Advanced",
  systemStatus: "ONLINE • TELEMETRY ACTIVE",
  activeFocus: "DATA SCIENCE & PREDICTIVE ANALYTICS",
};

// 2. "MY DATA" SIGNATURE METRICS
export const DATA_SIGNATURE_METRICS = [
  { label: "YEARS LEARNING & EXP", value: "03+", unit: "Years", change: "+100% YoY" },
  { label: "PROJECTS BUILT", value: "08+", unit: "End-to-End", change: "4 In Lab" },
  { label: "ANALYTICS DASHBOARDS", value: "04+", unit: "Production", change: "Real-time" },
  { label: "SQL QUERIES EXECUTED", value: "10K+", unit: "Optimized", change: "Sub-second" },
];

export const SKILL_PROGRESS_METERS = [
  { name: "SQL & Query Optimization", percent: 90, tier: "Expert", desc: "Complex joins, CTEs, Window functions, Stored procedures" },
  { name: "Python (Pandas, NumPy, Scikit-learn)", percent: 80, tier: "Advanced", desc: "Data manipulation, automated pipelines, statistical modeling" },
  { name: "Power BI & Data Storytelling", percent: 88, tier: "Advanced", desc: "DAX, Star schema, interactive drill-downs, executive KPIs" },
  { name: "PostgreSQL & Database Architecture", percent: 85, tier: "Advanced", desc: "Indexing, relational integrity, execution plans, DDL/DML" },
  { name: "Exploratory Data Analysis (EDA)", percent: 90, tier: "Expert", desc: "Anomaly detection, pattern discovery, trend forecasting" },
  { name: "Applied Statistics & Machine Learning", percent: 75, tier: "Proficient", desc: "Hypothesis testing, regression, classification, clustering" },
];

// 3. CAREER & LEARNING TIMELINE ("THE JOURNEY")
export const JOURNEY_MILESTONES = [
  {
    year: "2025",
    quarter: "Q1 - Q2",
    title: "Analytics Foundation & SQL Mastery",
    subtitle: "Enterprise Database Querying & MIS Reporting",
    description: "Deep-dived into relational database querying, structured stored procedures, business metric extraction, and management information systems (MIS).",
    skills: ["SQL", "PostgreSQL", "Database Schema", "Excel MIS", "Data Cleaning"],
    highlight: "Designed high-performance SQL stored procedures reducing report extraction latency.",
    status: "Completed",
  },
  {
    year: "2025",
    quarter: "Q3 - Q4",
    title: "Business Intelligence & Automated Pipelines",
    subtitle: "Power BI & Python Data Engineering",
    description: "Transitioned to building interactive executive dashboards in Power BI and writing automated Python ETL scripts using Pandas.",
    skills: ["Power BI", "DAX", "Python", "Pandas", "ETL Pipelines"],
    highlight: "Delivered interactive KPI monitoring dashboards with dynamic Star-schema modeling.",
    status: "Completed",
  },
  {
    year: "2026",
    quarter: "Q1 - Present",
    title: "Data Science Specialization & DS-365",
    subtitle: "Statistical Modeling & Predictive Analytics",
    description: "Actively executing the DS-365 curriculum: rigorous statistical hypothesis testing, machine learning algorithms, predictive feature engineering, and model evaluation.",
    skills: ["Machine Learning", "Scikit-Learn", "Applied Statistics", "Feature Engineering"],
    highlight: "Developing predictive analytics experiments and modular end-to-end data systems.",
    status: "In Progress",
  },
  {
    year: "2026",
    quarter: "Ongoing",
    title: "LifeOS Behavioral Intelligence",
    subtitle: "Personal Data Science & Analytics Engine",
    description: "Architected a full-stack personal operating system that logs and analyzes daily habits, study hours, career applications, and performance metrics.",
    skills: ["Full Stack Data System", "PostgreSQL", "React", "Data Visualization"],
    highlight: "Created predictive discipline scoring algorithms and interactive habit analytics.",
    status: "Active",
  },
];

// 4. DATA LAB PROJECTS WITH 6-STAGE CASE STUDIES
export const DATA_LAB_PROJECTS = [
  {
    id: "urban-mobility",
    title: "Urban Mobility Analytics & Demand Forecasting",
    category: "Geospatial & Time-Series Analytics",
    tags: ["Python", "PostgreSQL", "Pandas", "Time Series", "Geospatial"],
    icon: "Navigation",
    summary: "Analyzed millions of rideshare pickup records to discover spatial-temporal bottleneck patterns, peak surge hours, and optimize driver dispatch efficiency.",
    chartType: "timeSeriesDemand",
    kpis: [
      { label: "Data Records", value: "4.5M+" },
      { label: "Peak Demand Surge", value: "18:00 - 21:00" },
      { label: "Borough Concentration", value: "68% Manhattan" },
      { label: "Predictive Gain", value: "+23% Dispatch Align" },
    ],
    // 6-Stage Case Study Structure
    caseStudy: {
      problem: "Urban rideshare fleets experience severe demand-supply imbalances during sudden weather shifts and evening peak hours, resulting in high passenger wait times and lost driver revenue.",
      data: "Uber NYC Pickup dataset spanning multi-month temporal coordinates, weather condition matrices, and geospatial borough zoning polygons.",
      approach: "Built an end-to-end PostgreSQL ETL pipeline to ingest raw coordinates, applied spatial aggregation via geospatial clustering, and aggregated rolling hourly demand windows using Pandas.",
      analysis: "Evaluated pickup velocity across boroughs. Identified that Friday and Saturday evening spikes had 3.4x demand elasticity compared to weekday mornings. Discovered specific transfer hubs with extreme variance.",
      insight: "Demand concentration is heavily skewed: 5 specific pickup zones account for 44% of total ride volume during precipitation events, proving that dynamic pre-positioning can eliminate 70% of surge lag.",
      result: "Formulated a proactive dispatch strategy model demonstrating a 23% potential reduction in average pickup idle time and optimized driver allocation schedules.",
    },
    codeSnippet: `-- SQL Window Aggregation for Peak Surge Velocity
SELECT 
    pickup_hour,
    borough_zone,
    COUNT(trip_id) AS total_pickups,
    ROUND(AVG(fare_amount), 2) AS avg_fare,
    RANK() OVER (PARTITION BY pickup_hour ORDER BY COUNT(trip_id) DESC) as demand_rank
FROM rideshare_trips
WHERE pickup_date BETWEEN '2025-01-01' AND '2025-06-30'
GROUP BY pickup_hour, borough_zone;`,
  },
  {
    id: "customer-retention",
    title: "Customer Retention & Churn Prediction Pipeline",
    category: "Predictive Classification & Business Analytics",
    tags: ["Python", "Scikit-learn", "EDA", "Feature Engineering", "SQL"],
    icon: "Users",
    summary: "Engineered a predictive churn classifier and cohort analysis engine to detect high-risk customer accounts 30 days before cancellation.",
    chartType: "retentionWaterfall",
    kpis: [
      { label: "Accounts Evaluated", value: "25,000+" },
      { label: "ROC-AUC Score", value: "0.87" },
      { label: "Early Detection Window", value: "30 Days" },
      { label: "Churn Risk Saved", value: "~18%" },
    ],
    caseStudy: {
      problem: "A subscription-based platform suffered a 4.2% monthly revenue leakage from unprompted customer churn, with account cancellations occurring without prior customer support tickets.",
      data: "Multi-table relational schema containing customer login frequency, feature usage depth, billing history, payment methods, and contract duration.",
      approach: "Conducted cohort retention analysis in SQL to establish baseline drop-offs. Engineered behavioral velocity features (e.g., login decay over 14 days vs 60 days) and trained a Random Forest / Logistic Regression pipeline.",
      analysis: "Identified that users with decreasing API utilization velocity over 3 consecutive weeks had an 82% probability of cancelling within the next billing cycle, regardless of tenure.",
      insight: "Onboarding depth in the first 14 days is the single largest predictor of long-term LTV: completing at least 3 core workflows reduced 90-day churn by 61%.",
      result: "Delivered an automated high-risk scoring dashboard that feeds directly into customer success alert queues, targeting at-risk accounts for timely retention outreach.",
    },
    codeSnippet: `# Feature Engineering: Usage Decay Velocity
df['usage_decay_ratio'] = (df['api_calls_last_14d'] / 14) / (df['api_calls_last_60d'] / 60 + 1e-5)
df['risk_flag'] = (df['usage_decay_ratio'] < 0.35) & (df['days_since_last_login'] > 7)`,
  },
  {
    id: "financial-risk",
    title: "Credit Risk Scoring & Default Probability Engine",
    category: "Risk Analytics & Statistical Modeling",
    tags: ["SQL", "PostgreSQL", "Python", "Power BI", "Statistics"],
    icon: "ShieldAlert",
    summary: "Built a statistical risk classification system analyzing debt-to-income ratios, payment delays, and liquidity metrics to estimate borrower default probabilities.",
    chartType: "riskDistribution",
    kpis: [
      { label: "Loan Records", value: "50,000+" },
      { label: "Gini Coefficient", value: "0.74" },
      { label: "False Positive Reduction", value: "-14%" },
      { label: "Accuracy", value: "89.2%" },
    ],
    caseStudy: {
      problem: "Traditional rule-based credit scoring rejected creditworthy thin-file applicants while failing to catch systemic default risks among multi-line borrowers.",
      data: "Anonymized consumer credit portfolios including revolving utilization, installment balances, delinquency count, employment stability, and macroeconomic indicators.",
      approach: "Calculated Weight of Evidence (WoE) and Information Value (IV) for 32 candidate variables to remove collinear features and construct robust credit scorecards.",
      analysis: "Demonstrated that revolving credit line utilization above 72% combined with more than 2 credit inquiries in 90 days increased default odds by 4.8x.",
      insight: "Non-linear interaction between payment delinquency frequency and debt-to-income ratio accounts for the vast majority of defaults; linear thresholds alone miss early deterioration signals.",
      result: "Built a Power BI executive risk monitoring dashboard displaying real-time portfolio concentration by risk tier, reducing approval turnaround time while protecting default tolerance.",
    },
    codeSnippet: `-- Calculating Risk Stratification Tiers
SELECT 
    borrower_segment,
    COUNT(*) as total_loans,
    SUM(CASE WHEN default_flag = 1 THEN 1 ELSE 0 END) as defaults,
    ROUND(100.0 * SUM(CASE WHEN default_flag = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as default_rate_pct
FROM credit_portfolio_mt
GROUP BY borrower_segment
ORDER BY default_rate_pct DESC;`,
  },
  {
    id: "lifeos-intelligence",
    title: "LifeOS: Behavioral & Habit Intelligence Matrix",
    category: "Full-Stack Data System & Quantified Self",
    tags: ["PostgreSQL", "React", "Data Visualization", "REST APIs", "Analytics"],
    icon: "Activity",
    summary: "Architected and deployed a personal operating system that tracks daily habits, career activities, and computes mathematical discipline momentum.",
    chartType: "habitCorrelation",
    kpis: [
      { label: "Days Tracked", value: "365 Matrix" },
      { label: "Discipline Score", value: "100-Pt Scale" },
      { label: "Quarterly Trends", value: "Q1 → Q4" },
      { label: "Architecture", value: "Full Stack" },
    ],
    caseStudy: {
      problem: "Productivity tracking tools are either fragmented or passive, lacking predictive correlation between physical fitness, study depth, and professional execution.",
      data: "Time-series daily discipline records logged in PostgreSQL, tracking 4 core vectors: Gym, Job Applications, Study/DS-365, and Project Engineering.",
      approach: "Constructed relational database schema with master-detail tracking, built Flask REST APIs, and created custom interactive heatmaps and tachometer gauges.",
      analysis: "Analyzed Pearson correlation coefficients across habits: consistent morning gym sessions showed a +0.78 correlation with 4+ hours of deep data science study.",
      insight: "Momentum follows an exponential decay model: missing 2 consecutive days reduces 30-day target completion probability by 47%, proving consistency is the critical variable.",
      result: "Deployed a live, accessible system serving as both a personal productivity engine and a showcase of full-stack data product engineering.",
    },
    codeSnippet: `-- Calculating Weighted Daily Discipline Score
SELECT 
    date,
    gym_completed,
    job_completed,
    study_completed,
    project_completed,
    ROUND(
      (CASE WHEN gym_completed THEN 25.0 ELSE 0.0 END) +
      (CASE WHEN job_completed THEN 25.0 ELSE 0.0 END) +
      (CASE WHEN study_completed THEN 25.0 ELSE 0.0 END) +
      (CASE WHEN project_completed THEN 25.0 ELSE 0.0 END), 2
    ) AS daily_score
FROM discipline_daily
ORDER BY date DESC;`,
  },
];

// 5. "HOW I THINK" — 9-STAGE PROBLEM SOLVING FLOW
export const PROBLEM_SOLVING_STEPS = [
  {
    step: "01",
    phase: "BUSINESS PROBLEM",
    title: "Understand the Core Reality",
    description: "Never start with the tool. Start with the actual operational or business pain point. What decision is currently blocked by lack of clarity?",
    tools: ["Stakeholder Context", "Domain Logic", "Impact Assessment"],
  },
  {
    step: "02",
    phase: "ASK THE RIGHT QUESTION",
    title: "Frame as a Data Hypothesis",
    description: "Translate vague business desires into precise, testable analytical questions that can be proven or disproven with metrics.",
    tools: ["Hypothesis Formulation", "Target Metric Definition", "Boundary Constraints"],
  },
  {
    step: "03",
    phase: "COLLECT & INGEST",
    title: "Source Relevant Data",
    description: "Identify data sources, schemas, and historical logs. Verify data lineage, grain, and completeness before running any calculation.",
    tools: ["SQL Extraction", "REST APIs", "Schema Discovery"],
  },
  {
    step: "04",
    phase: "CLEAN & VALIDATE",
    title: "Ensure Ground Truth",
    description: "Handle nulls, duplicates, outliers, and type mismatches. If the input is corrupted, the insight will be misleading.",
    tools: ["Pandas", "PostgreSQL DML", "Sanity Check Queries"],
  },
  {
    step: "05",
    phase: "EXPLORE & HYPOTHESIZE",
    title: "Exploratory Data Analysis",
    description: "Slice across time, geography, user segments, and categories. Visualize distributions to uncover hidden variance.",
    tools: ["Descriptive Stats", "Histograms", "Correlation Matrices"],
  },
  {
    step: "06",
    phase: "FIND PATTERNS",
    title: "Extract Underlying Drivers",
    description: "Isolate seasonality, feature correlations, and behavioral clusters. Separate noise from statistical significance.",
    tools: ["Window Functions", "Cohort Analysis", "Dimensional Slicing"],
  },
  {
    step: "07",
    phase: "MODEL & TEST",
    title: "Apply Statistical Rigor",
    description: "Build predictive models or scenario simulations when forecasting is needed. Validate accuracy with cross-validation.",
    tools: ["Scikit-learn", "Regression/Classification", "Evaluation Metrics"],
  },
  {
    step: "08",
    phase: "MEASURE IMPACT",
    title: "Quantify the Upside",
    description: "Translate analytical findings into actionable business terms: cost saved, revenue increased, efficiency gained, or risk avoided.",
    tools: ["KPI Modeling", "A/B Test Design", "Sensitivity Analysis"],
  },
  {
    step: "09",
    phase: "DECIDE & COMMUNICATE",
    title: "Clear, Unambiguous Action",
    description: "Deliver findings via intuitive dashboards and executive summaries. Data is only useful if it drives confident decisions.",
    tools: ["Power BI", "Data Storytelling", "Executive Summaries"],
  },
];

// 6. INTERACTIVE SKILL TREE MAP
export const SKILL_TREE_DATA = {
  id: "data-root",
  name: "DATA & ANALYTICS",
  level: "Mastery Core",
  children: [
    {
      id: "sql-core",
      name: "SQL & Relational DBs",
      level: "90% • Expert",
      useCase: "Complex analytical queries, window functions, CTEs, subqueries, table indexing, and stored procedures.",
      projects: ["Urban Mobility", "LifeOS Database", "Job Tracking Engine"],
      subItems: ["PostgreSQL", "SQL Server", "Query Optimization", "Window Functions", "CTEs & Joins"],
    },
    {
      id: "python-core",
      name: "Python Ecosystem",
      level: "80% • Advanced",
      useCase: "End-to-end data pipelines, exploratory data analysis, data wrangling, and statistical machine learning.",
      projects: ["Customer Churn Predictor", "Urban Mobility Analytics", "ETL Automation"],
      subItems: ["Pandas", "NumPy", "Scikit-Learn", "Matplotlib / Seaborn", "Automation Scripts"],
    },
    {
      id: "bi-core",
      name: "Business Intelligence",
      level: "88% • Advanced",
      useCase: "Translating multi-table databases into interactive executive dashboards with Star Schema modeling.",
      projects: ["Executive Sales Dashboard", "Credit Risk Visualizer", "Discipline Analytics"],
      subItems: ["Power BI", "DAX Formulas", "Star Schema Modeling", "KPI Dashboards", "Data Storytelling"],
    },
    {
      id: "stats-ml-core",
      name: "Applied Stats & ML",
      level: "75% • Proficient",
      useCase: "Hypothesis testing, probability distributions, regression, classification algorithms, and model evaluation.",
      projects: ["Churn Classification", "Credit Default Scoring", "DS-365 Curriculum"],
      subItems: ["Hypothesis Testing", "Linear & Logistic Regression", "Decision Trees & Random Forests", "Feature Engineering"],
    },
  ],
};

// 7. "IF MY CAREER WERE A DATASET" ANALYTICS
export const CAREER_DATASET = {
  skillDistribution: [
    { skill: "SQL & Querying", percentage: 90, color: "#38bdf8" },
    { skill: "Data Analytics & EDA", percentage: 90, color: "#06b6d4" },
    { skill: "Power BI & Dashboards", percentage: 88, color: "#eab308" },
    { skill: "PostgreSQL Architecture", percentage: 85, color: "#3b82f6" },
    { skill: "Python (Pandas / NumPy)", percentage: 80, color: "#10b981" },
    { skill: "Machine Learning Foundations", percentage: 75, color: "#a855f7" },
  ],
  focusDistribution: [
    { area: "Business & Problem Analytics", weight: 35, color: "#38bdf8" },
    { area: "Database Design & SQL Engineering", weight: 30, color: "#3b82f6" },
    { area: "Data Science & ML Research", weight: 20, color: "#a855f7" },
    { area: "Dashboard & UI Product Engineering", weight: 15, color: "#10b981" },
  ],
  weeklyProductivityCadence: [
    { day: "Mon", deepWorkHours: 7.5, sqlQueries: 42 },
    { day: "Tue", deepWorkHours: 8.0, sqlQueries: 56 },
    { day: "Wed", deepWorkHours: 8.5, sqlQueries: 64 },
    { day: "Thu", deepWorkHours: 7.8, sqlQueries: 48 },
    { day: "Fri", deepWorkHours: 9.0, sqlQueries: 72 },
    { day: "Sat", deepWorkHours: 6.5, sqlQueries: 35 },
    { day: "Sun", deepWorkHours: 5.0, sqlQueries: 20 },
  ],
};

// 8. "CURRENTLY BUILDING" LIVE RADAR
export const CURRENTLY_BUILDING = [
  {
    id: "ds-365",
    tag: "CURRICULUM",
    title: "DS-365 Challenge",
    subtitle: "365 Days of Continuous Data Science & ML Mastery",
    desc: "Daily deliberate practice spanning statistical theory, algorithmic implementations from scratch, real-world Kaggle datasets, and mathematical optimization.",
    badge: "DAILY ACTIVE",
    color: "#38bdf8",
  },
  {
    id: "lifeos-prod",
    tag: "DATA SYSTEM",
    title: "LifeOS Operating System",
    subtitle: "Full-Stack Personal Discipline & Productivity Engine",
    desc: "Production-grade platform tracking quantitative habits, career applications, and performance telemetry with real-time PostgreSQL database persistence.",
    badge: "DEPLOYED & LIVE",
    color: "#10b981",
  },
  {
    id: "data-lab",
    tag: "CASE STUDIES",
    title: "Production Data Lab",
    subtitle: "End-to-End Predictive & Exploratory Analytics",
    desc: "Building production-grade case studies addressing real-world operational bottlenecks: urban logistics, customer churn mitigation, and credit risk modeling.",
    badge: "EXPANDING",
    color: "#eab308",
  },
];

// 9. RESUME EXPERIENCE & EDUCATION
export const RESUME_EXPERIENCE = [
  {
    id: "exp-1",
    role: "Database & Data Analytics Professional",
    period: "2025 → Present",
    company: "Professional Analytics & Data Management",
    summary: "Managing enterprise database operations, writing optimized SQL queries, extracting actionable business metrics, and delivering automated reporting solutions.",
    keyPoints: [
      "Designed and executed complex multi-table SQL queries, CTEs, and stored procedures to transform raw transactional data into structured reporting views.",
      "Engineered automated MIS report extractions, eliminating manual spreadsheet bottlenecks and accelerating executive review cycles.",
      "Collaborated with cross-functional stakeholders to audit data discrepancies, establish referential integrity, and resolve data quality issues.",
      "Constructed interactive visual summaries highlighting key operational KPIs and performance anomalies.",
    ],
    skills: ["SQL", "PostgreSQL", "Power BI", "Data Cleaning", "MIS Reporting", "Stored Procedures"],
  },
  {
    id: "exp-2",
    role: "Data Science & Analytics Practitioner",
    period: "2025 → Present",
    company: "DS-365 & Applied Predictive Analytics",
    summary: "Independent research and development of machine learning pipelines, predictive feature sets, and end-to-end data applications.",
    keyPoints: [
      "Built predictive classification models for customer churn detection and credit risk stratification using Python, Pandas, and Scikit-learn.",
      "Architected LifeOS full-stack data system with custom PostgreSQL schema, Flask REST APIs, and dynamic React telemetry dashboards.",
      "Conducted exploratory data analysis on multi-million row datasets to discover demand surge patterns and geospatial efficiency gains.",
    ],
    skills: ["Python", "Pandas", "Scikit-Learn", "Machine Learning", "Applied Statistics", "System Architecture"],
  },
];

export const EDUCATION_DATA = [
  {
    degree: "Bachelor's Degree",
    field: "Computer Applications / Technology",
    focus: "Database Systems, Algorithms, Mathematics & Analytics",
    status: "Completed",
  },
  {
    degree: "Continuous Specialization",
    field: "Data Science, Machine Learning & Statistics",
    focus: "Predictive Analytics, Python for Data Science, SQL Mastery & BI Storytelling",
    status: "Active (DS-365)",
  },
];
