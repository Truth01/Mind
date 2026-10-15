import os

# Define the file structure and content
files = {
    "README.md": """# Mind AI - Phase 1: Foundation
## Setup Instructions
1. Run `docker-compose up -d` to start PostgreSQL and Redis.
2. Install backend dependencies: `pip install fastapi uvicorn sqlalchemy pydantic openai celery redis`
3. Install frontend dependencies: `npm install` (Ensure Next.js, Tailwind, and ShadCN are initialized).
4. Start backend: `uvicorn backend.app.main:app --reload`
5. Start frontend: `npm run dev`
""",

    "docker-compose.yml": """version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: mind_user
      POSTGRES_PASSWORD: mind_password
      POSTGRES_DB: mind_db
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
""",

    "backend/app/models.py": """from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True) # Clerk User ID
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    subscription = Column(String, default="starter")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    businesses = relationship("Business", back_populates="owner")

class Business(Base):
    __tablename__ = "businesses"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(String, ForeignKey("users.id"))
    business_name = Column(String, nullable=False)
    industry = Column(String)
    country = Column(String)
    website = Column(String)
    description = Column(Text)
    goals = Column(JSON) 
    size = Column(String)
    health_score = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    owner = relationship("User", back_populates="businesses")
    tasks = relationship("DailyTask", back_populates="business")
    reports = relationship("Report", back_populates="business")

class DailyTask(Base):
    __tablename__ = "daily_tasks"
    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"))
    title = Column(String, nullable=False)
    description = Column(Text)
    priority = Column(String, default="MEDIUM") 
    status = Column(String, default="PENDING") 
    deadline = Column(DateTime(timezone=True))
    business = relationship("Business", back_populates="tasks")

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"))
    agent = Column(String) 
    summary = Column(Text)
    recommendations = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    business = relationship("Business", back_populates="reports")
""",

    "backend/app/main.py": """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, onboarding, dashboard

app = FastAPI(title="Mind AI Business OS", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(onboarding.router, prefix="/api/onboarding", tags=["Onboarding"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])

@app.get("/")
def read_root():
    return {"message": "Mind AI Business Operating System is running."}
""",

    "backend/app/api/onboarding.py": """from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services.ai_interview import run_ai_interview, generate_business_profile
from app.models import Business, User
from app.core.auth import get_current_user
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

class InterviewRequest(BaseModel):
    business_id: int
    message: str
    history: List[dict]

class ProfileData(BaseModel):
    business_name: str
    industry: str
    country: str
    website: Optional[str]
    description: str
    goals: List[str]
    size: str

@router.post("/interview")
async def chat_interview(req: InterviewRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    business = await db.get(Business, req.business_id)
    if not business or business.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    response = await run_ai_interview(req.message, req.history)
    return {"reply": response}

@router.post("/generate-profile")
async def build_profile(business_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    business = await db.get(Business, business_id)
    if not business or business.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    profile_data: ProfileData = await generate_business_profile(business_id)
    
    business.business_name = profile_data.business_name
    business.industry = profile_data.industry
    business.country = profile_data.country
    business.website = profile_data.website
    business.description = profile_data.description
    business.goals = profile_data.goals
    business.size = profile_data.size
    
    await db.commit()
    return {"status": "success", "business": business}
""",

    "backend/app/services/ai_interview.py": """import openai
from pydantic import BaseModel
from typing import List
from app.core.config import settings

openai.api_key = settings.OPENAI_API_KEY

class ProfileOutput(BaseModel):
    business_name: str
    industry: str
    country: str
    website: str
    description: str
    goals: List[str]
    size: str

async def run_ai_interview(user_message: str, history: List[dict]) -> str:
    system_prompt = \"\"\"You are Mind, an AI Business Co-Founder. You are conducting an initial interview with an entrepreneur to understand their business. 
    Ask concise, insightful questions one by one about: what they sell, target customers, revenue, challenges, competitors, and marketing channels.
    Keep the tone professional, encouraging, and highly analytical.\"\"\"
    
    messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_message}]
    
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7
    )
    return response.choices[0].message.content

async def generate_business_profile(business_id: int) -> ProfileOutput:
    chat_history_summary = "User sells SaaS for real estate, targets agents, makes $10k/mrr, biggest challenge is lead gen..."
    
    prompt = f\"\"\"Based on this interview summary: '{chat_history_summary}', extract the business profile.\"\"\"
    
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": "Extract structured data."}, {"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    return ProfileOutput.parse_raw(response.choices[0].message.content)
""",

    "backend/app/worker.py": """from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "mind_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

@celery_app.task
def send_morning_brief(business_id: int):
    print(f"Generating Morning Brief for Business {business_id}")
    return "Brief sent"
""",

    "frontend/src/app/(dashboard)/layout.tsx": """import { Sidebar } from "@/components/dashboard/sidebar"
import { TopNav } from "@/components/dashboard/top-nav"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopNav />
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
""",

    "frontend/src/app/onboarding/page.tsx": """"use client"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Send, Bot, User } from "lucide-react"

export default function OnboardingPage() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hello! I'm Mind, your AI Co-Founder. Let's build your business profile. First, what exactly do you sell, and who are your ideal customers?" }
  ])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)

  const handleSend = async () => {
    if (!input.trim()) return
    const newMessages = [...messages, { role: "user", content: input }]
    setMessages(newMessages)
    setInput("")
    setIsLoading(true)

    setTimeout(() => {
        setMessages([...newMessages, { role: "assistant", content: "Great. And what is your current monthly revenue, and what's your biggest challenge right now?" }])
        setIsLoading(false)
    }, 1000)
  }

  return (
    <div className="max-w-3xl mx-auto py-10">
      <Card className="h-[70vh] flex flex-col">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Bot className="w-6 h-6 text-blue-600"/> Mind AI Interview</CardTitle>
        </CardHeader>
        <CardContent className="flex-1 overflow-y-auto space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
              {msg.role === 'assistant' && <Bot className="w-8 h-8 p-1.5 bg-blue-100 rounded-full text-blue-600" />}
              <div className={`p-3 rounded-lg max-w-md ${msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}>
                {msg.content}
              </div>
              {msg.role === 'user' && <User className="w-8 h-8 p-1.5 bg-gray-200 rounded-full" />}
            </div>
          ))}
          {isLoading && <div className="text-gray-500 italic">Mind is thinking...</div>}
        </CardContent>
        <div className="p-4 border-t flex gap-2">
          <Input 
            placeholder="Type your answer..." 
            value={input} 
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          />
          <Button onClick={handleSend} disabled={isLoading}><Send className="w-4 h-4"/></Button>
        </div>
      </Card>
      <div className="mt-4 flex justify-end">
        <Button variant="outline" onClick={() => alert("Generating Profile...")}>Finish Interview & Build Profile</Button>
      </div>
    </div>
  )
}
""",

    "frontend/src/app/(dashboard)/page.tsx": """import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { TrendingUp, AlertTriangle, CheckCircle2 } from "lucide-react"

export default function DashboardHome() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Good Morning, John 👋</h1>
        <p className="text-gray-500">Here is your business overview for today.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Business Health Score</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between mb-2">
            <span className="text-4xl font-bold text-blue-600">83<span className="text-lg text-gray-400">/100</span></span>
            <TrendingUp className="w-8 h-8 text-green-500" />
          </div>
          <Progress value={83} className="h-2" />
          <div className="grid grid-cols-3 md:grid-cols-6 gap-4 mt-6 text-center">
            {["Marketing", "Sales", "SEO", "Finance", "Ops", "CX"].map((cat) => (
              <div key={cat} className="p-2 bg-gray-50 rounded">
                <div className="text-xs text-gray-500">{cat}</div>
                <div className="font-bold">{Math.floor(Math.random() * 30) + 60}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid md:grid-cols-2 gap-6">
        <Card>
          <CardHeader><CardTitle>Today's Priorities</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {["Finish landing page", "Call 3 leads", "Write LinkedIn post"].map((task, i) => (
              <div key={i} className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded">
                <CheckCircle2 className="w-5 h-5 text-gray-300" />
                <span>{task}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Threats & Alerts</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-start gap-3 p-2 bg-red-50 rounded border border-red-100">
              <AlertTriangle className="w-5 h-5 text-red-500 mt-0.5" />
              <div>
                <p className="font-medium text-red-800">Competitor ABC reduced prices</p>
                <p className="text-sm text-red-600">Detected 2 hours ago. Review pricing strategy.</p>
              </div>
            </div>
            <div className="flex items-start gap-3 p-2 bg-yellow-50 rounded border border-yellow-100">
              <AlertTriangle className="w-5 h-5 text-yellow-500 mt-0.5" />
              <div>
                <p className="font-medium text-yellow-800">Website speed decreased</p>
                <p className="text-sm text-yellow-600">LCP dropped by 1.2s. Check server load.</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
""",

    "frontend/src/app/(dashboard)/settings/page.tsx": """import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export default function SettingsPage() {
  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-3xl font-bold">Settings</h1>
      
      <Card>
        <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input defaultValue="John Doe" />
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input defaultValue="john@company.com" disabled />
            </div>
          </div>
          <Button>Save Changes</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Integrations</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {["Google Analytics", "Stripe", "Mailchimp", "Slack"].map((integration) => (
            <div key={integration} className="flex items-center justify-between p-3 border rounded">
              <span className="font-medium">{integration}</span>
              <Button variant="outline" size="sm">Connect</Button>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
"""
}

# Create directories and write files
for filepath, content in files.items():
    dir_name = os.path.dirname(filepath)
    if dir_name:  # Only create directories if a path actually exists
      os.makedirs(dir_name, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created: {filepath}")

print("\n✅ Phase 1 Foundation files generated successfully!")