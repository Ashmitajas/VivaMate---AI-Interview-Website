import json, os, uuid
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, jsonify, render_template, request

app=Flask(__name__)
DATA_DIR=Path(__file__).parent/'data'; DATA_DIR.mkdir(exist_ok=True)
EVENTS_FILE=DATA_DIR/'events.jsonl'
OPENAI_API_KEY=os.getenv('OPENAI_API_KEY')
MODEL=os.getenv('OPENAI_MODEL','gpt-4o-mini')
QUESTIONS=[
'Can you walk me through a project you are genuinely proud of and the problem it solved?',
'Tell me about a difficult technical decision you made in that project. What options did you consider?',
'Imagine your solution suddenly had 10× more users. What would break first, and how would you redesign it?',
'Tell me about a time something went wrong. What did you learn and what did you change afterward?',
'Why are you interested in this role, and what is one thing you could contribute from day one?']
DEMO=[('Strong start','You gave the interviewer a clear direction. Make the answer stronger by naming the problem, your specific contribution, and one measurable result.'),('Good technical judgment','Explain the trade-off behind your decision, then briefly say why the alternative was weaker for your constraints.'),('Good scaling instinct','Prioritize one likely bottleneck and explain how you would validate it before redesigning the whole system.'),('Useful reflection','Own the outcome, explain what changed in your behavior, and close with the lesson you would carry forward.'),('Strong close','Connect one concrete strength to the role and support it with evidence from a project or experience.')]
def log_event(event,session_id,meta=None):
    with EVENTS_FILE.open('a',encoding='utf-8') as f:f.write(json.dumps({'timestamp':datetime.now(timezone.utc).isoformat(),'event':event,'session_id':session_id,'meta':meta or {}})+'\n')
def ai_feedback(question,answer,index):
    if not OPENAI_API_KEY:
        t,f=DEMO[min(index,len(DEMO)-1)];return {'title':t,'feedback':f,'mode':'demo'}
    try:
        from openai import OpenAI
        client=OpenAI(api_key=OPENAI_API_KEY,timeout=20)
        prompt=f'''You are Ashmita, a concise interview coach. Evaluate the candidate answer.
Question: {question}\nAnswer: {answer}\nReturn exactly two lines: TITLE: 2-4 words\nFEEDBACK: 1-2 sentences with one specific improvement. Do not invent facts.'''
        r=client.responses.create(model=MODEL,input=prompt); text=r.output_text.strip(); title='Useful feedback'; feedback=text
        for line in text.splitlines():
            if line.upper().startswith('TITLE:'): title=line.split(':',1)[1].strip()
            if line.upper().startswith('FEEDBACK:'): feedback=line.split(':',1)[1].strip()
        return {'title':title[:80],'feedback':feedback[:600],'mode':'live'}
    except Exception:
        t,f=DEMO[min(index,len(DEMO)-1)];return {'title':t,'feedback':f,'mode':'demo_fallback'}
@app.get('/')
def home():return render_template('index.html')
@app.get('/api/health')
def health():return jsonify(status='ok',ai_mode='live' if OPENAI_API_KEY else 'demo',questions=len(QUESTIONS))
@app.post('/api/event')
def event():
    p=request.get_json(silent=True) or {}; sid=str(p.get('session_id') or uuid.uuid4())[:100]; name=str(p.get('event') or 'unknown')[:80]; meta=p.get('meta') if isinstance(p.get('meta'),dict) else {};log_event(name,sid,meta);return jsonify(ok=True,session_id=sid)
@app.post('/api/answer')
def answer():
    p=request.get_json(silent=True) or {};sid=str(p.get('session_id') or uuid.uuid4())[:100]
    try:i=int(p.get('index',0))
    except:return jsonify(error='Invalid question index.'),400
    if i<0 or i>=len(QUESTIONS):return jsonify(error='Invalid question index.'),400
    text=str(p.get('answer') or '').strip()
    if not text:return jsonify(error='Answer is required.'),400
    if len(text)>6000:return jsonify(error='Please keep your answer under 6,000 characters.'),400
    result=ai_feedback(QUESTIONS[i],text,i);log_event('answer_submitted',sid,{'question_index':i,'answer_length':len(text)});n=i+1
    return jsonify(feedback=result,next_question=QUESTIONS[n] if n<len(QUESTIONS) else None,next_index=n,complete=n>=len(QUESTIONS))
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)),debug=os.getenv('FLASK_DEBUG','0')=='1')
