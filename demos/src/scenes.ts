// Each feature scene pairs a real capture from scripts/capture.mjs with the prompt the user typed.
export type FeatureScene = {
  id: string;
  kicker: string;
  title: string;
  body: string;
  prompt?: string;
  image: string;
  seconds: number;
};

export const featureScenes: FeatureScene[] = [
  {
    id: "date-tool",
    kicker: "TOOLS · CALENDAR",
    title: "Ask for today, get today",
    body: "Dana reads the current date and time in your timezone, so it never asks you for a date range.",
    prompt: "What is today's date and the current time in IST?",
    image: "date-tool.png",
    seconds: 8,
  },
  {
    id: "math-tool",
    kicker: "TOOLS · MATH",
    title: "Exact arithmetic as a tool call",
    body: "Calculations go through a math tool, so every number in an answer can be traced in the thinking trace.",
    prompt: "Calculate 12.5% of 480, then add 37.",
    image: "math-tool.png",
    seconds: 7,
  },
  {
    id: "holidays-tool",
    kicker: "TOOLS · HOLIDAYS",
    title: "Country holidays on demand",
    body: "Calendar and holiday tools list public holidays for a country, so campaigns can be planned around them.",
    prompt: "List the public holidays in India for the rest of this year.",
    image: "holidays-tool.png",
    seconds: 9,
  },
  {
    id: "connectors",
    kicker: "CONNECTORS",
    title: "Your organisation's data connectors",
    body: "Multi-tenant connectors are listed for the signed-in organisation, with channel and row counts.",
    prompt: "What data connectors do I have connected?",
    image: "connectors.png",
    seconds: 9,
  },
  {
    id: "jobs-page",
    kicker: "JOBS",
    title: "Every training run in one place",
    body: "Totals, active runs, and a table of each job's kind, progress, and status for your organisation.",
    image: "jobs-page.png",
    seconds: 7,
  },
  {
    id: "job-status",
    kicker: "JOB LOOKUP TOOLS",
    title: "Ask where your job stands",
    body: "check_last_job reads status, training window, and timestamps straight from the job store.",
    prompt: "What is the status of my last training job?",
    image: "job-status.png",
    seconds: 8,
  },
  {
    id: "model-location",
    kicker: "MODEL ARTIFACTS",
    title: "Find the saved model",
    body: "The artifact path, size, channels, controls, and fit diagnostics for the latest model, in one answer.",
    prompt: "Where is my latest trained model saved?",
    image: "model-location.png",
    seconds: 9,
  },
  {
    id: "train-hitl",
    kicker: "HUMAN IN THE LOOP",
    title: "Dana asks before it trains",
    body: "Missing inputs become a question card. You answer in the chat and the agent continues with your choice.",
    prompt: "Train an MMM model on my data.",
    image: "train-hitl.png",
    seconds: 9,
  },
];
