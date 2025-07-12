import gradio as gr
import requests
import json
from datetime import datetime
from pathlib import Path
import pandas as pd

API_BASE_URL = "http://localhost:8000/api/v1"


def upload_pdf_for_terms(file):
    if file is None:
        return "Please upload a PDF file"
        
    try:
        with open(file.name, 'rb') as f:
            files = {'file': (Path(file.name).name, f, 'application/pdf')}
            response = requests.post(f"{API_BASE_URL}/terms/extract-from-pdf", files=files)
            
        if response.status_code == 200:
            return f"✅ PDF processing started: {response.json()['filename']}"
        else:
            return f"❌ Error: {response.text}"
    except Exception as e:
        return f"❌ Error: {str(e)}"


def search_terms(query):
    try:
        response = requests.get(f"{API_BASE_URL}/terms/search", params={"query": query})
        if response.status_code == 200:
            results = response.json()["results"]
            if results:
                df = pd.DataFrame(results)
                df['similarity'] = df['similarity'].round(3)
                return df
            else:
                return pd.DataFrame({"Message": ["No results found"]})
        else:
            return pd.DataFrame({"Error": [response.text]})
    except Exception as e:
        return pd.DataFrame({"Error": [str(e)]})


def transcribe_audio(file, apply_correction):
    if file is None:
        return "Please upload an audio file", ""
        
    try:
        with open(file.name, 'rb') as f:
            files = {'file': (Path(file.name).name, f)}
            data = {'apply_correction': apply_correction}
            response = requests.post(f"{API_BASE_URL}/transcription/transcribe", files=files, data=data)
            
        if response.status_code == 200:
            task_id = response.json()["task_id"]
            return f"✅ Transcription started. Task ID: {task_id}", task_id
        else:
            return f"❌ Error: {response.text}", ""
    except Exception as e:
        return f"❌ Error: {str(e)}", ""


def check_transcription_status(task_id):
    if not task_id:
        return "Please provide a task ID"
        
    try:
        response = requests.get(f"{API_BASE_URL}/transcription/status/{task_id}")
        if response.status_code == 200:
            status = response.json()
            return json.dumps(status, indent=2, ensure_ascii=False)
        else:
            return f"Error: {response.text}"
    except Exception as e:
        return f"Error: {str(e)}"


def generate_meeting_minutes(transcription_id, meeting_title, meeting_date, participants):
    if not all([transcription_id, meeting_title, meeting_date, participants]):
        return "Please fill all fields"
        
    try:
        participants_list = [p.strip() for p in participants.split(',')]
        data = {
            "transcription_id": int(transcription_id),
            "meeting_title": meeting_title,
            "meeting_date": meeting_date + "T00:00:00",
            "participants": participants_list
        }
        
        response = requests.post(f"{API_BASE_URL}/meetings/generate", json=data)
        
        if response.status_code == 200:
            return f"✅ Meeting minutes generated. ID: {response.json()['meeting_minutes_id']}"
        else:
            return f"❌ Error: {response.text}"
    except Exception as e:
        return f"❌ Error: {str(e)}"


def get_action_items(status_filter=None, priority_filter=None):
    try:
        params = {}
        if status_filter and status_filter != "All":
            params["status"] = status_filter.lower()
        if priority_filter and priority_filter != "All":
            params["priority"] = priority_filter.lower()
            
        response = requests.get(f"{API_BASE_URL}/action-items", params=params)
        
        if response.status_code == 200:
            items = response.json()["items"]
            if items:
                df = pd.DataFrame(items)
                df['tags'] = df['tags'].apply(lambda x: ', '.join(x))
                return df[['id', 'title', 'assignee', 'due_date', 'priority', 'status', 'tags']]
            else:
                return pd.DataFrame({"Message": ["No action items found"]})
        else:
            return pd.DataFrame({"Error": [response.text]})
    except Exception as e:
        return pd.DataFrame({"Error": [str(e)]})


def get_tag_statistics():
    try:
        response = requests.get(f"{API_BASE_URL}/tags/statistics")
        if response.status_code == 200:
            stats = response.json()
            return json.dumps(stats, indent=2, ensure_ascii=False)
        else:
            return f"Error: {response.text}"
    except Exception as e:
        return f"Error: {str(e)}"


with gr.Blocks(title="Action Items System") as app:
    gr.Markdown("# 建設業界向け議事録・アクションアイテム管理システム")
    
    with gr.Tab("用語管理"):
        gr.Markdown("## PDF資料から専門用語を抽出")
        
        with gr.Row():
            pdf_file = gr.File(label="PDFファイルをアップロード", file_types=[".pdf"])
            pdf_upload_btn = gr.Button("用語抽出開始", variant="primary")
        
        pdf_result = gr.Textbox(label="処理結果")
        
        gr.Markdown("## 用語検索")
        with gr.Row():
            search_query = gr.Textbox(label="検索キーワード", placeholder="例: コンクリート")
            search_btn = gr.Button("検索", variant="primary")
        
        search_results = gr.Dataframe(label="検索結果")
        
        pdf_upload_btn.click(upload_pdf_for_terms, inputs=[pdf_file], outputs=[pdf_result])
        search_btn.click(search_terms, inputs=[search_query], outputs=[search_results])
    
    with gr.Tab("音声文字起こし"):
        gr.Markdown("## 会議音声の文字起こし")
        
        with gr.Row():
            audio_file = gr.File(label="音声ファイルをアップロード", file_types=[".mp3", ".mp4", ".wav", ".m4a"])
            apply_correction = gr.Checkbox(label="専門用語による自動修正を適用", value=True)
        
        transcribe_btn = gr.Button("文字起こし開始", variant="primary")
        
        with gr.Row():
            transcribe_result = gr.Textbox(label="処理結果")
            task_id_output = gr.Textbox(label="タスクID", visible=False)
        
        gr.Markdown("## 処理状況確認")
        with gr.Row():
            task_id_input = gr.Textbox(label="タスクID")
            check_status_btn = gr.Button("状況確認")
        
        status_result = gr.Textbox(label="処理状況", lines=10)
        
        transcribe_btn.click(
            transcribe_audio,
            inputs=[audio_file, apply_correction],
            outputs=[transcribe_result, task_id_output]
        )
        check_status_btn.click(
            check_transcription_status,
            inputs=[task_id_input],
            outputs=[status_result]
        )
    
    with gr.Tab("議事録生成"):
        gr.Markdown("## 文字起こし結果から議事録を生成")
        
        with gr.Row():
            with gr.Column():
                trans_id = gr.Number(label="文字起こしID", precision=0)
                meeting_title = gr.Textbox(label="会議名", placeholder="例: 第5回工程会議")
                meeting_date = gr.Textbox(label="会議日 (YYYY-MM-DD)", placeholder="2024-01-15")
                participants = gr.Textbox(label="参加者 (カンマ区切り)", placeholder="田中, 山田, 佐藤")
            
        generate_minutes_btn = gr.Button("議事録生成", variant="primary")
        minutes_result = gr.Textbox(label="生成結果")
        
        generate_minutes_btn.click(
            generate_meeting_minutes,
            inputs=[trans_id, meeting_title, meeting_date, participants],
            outputs=[minutes_result]
        )
    
    with gr.Tab("アクションアイテム"):
        gr.Markdown("## アクションアイテム一覧")
        
        with gr.Row():
            status_filter = gr.Dropdown(
                choices=["All", "Pending", "In Progress", "Completed", "Cancelled"],
                value="All",
                label="ステータスフィルター"
            )
            priority_filter = gr.Dropdown(
                choices=["All", "High", "Medium", "Low"],
                value="All",
                label="優先度フィルター"
            )
            refresh_btn = gr.Button("更新", variant="primary")
        
        action_items_table = gr.Dataframe(label="アクションアイテム")
        
        refresh_btn.click(
            get_action_items,
            inputs=[status_filter, priority_filter],
            outputs=[action_items_table]
        )
    
    with gr.Tab("タグ統計"):
        gr.Markdown("## タグ使用統計")
        
        get_stats_btn = gr.Button("統計情報取得", variant="primary")
        stats_output = gr.Textbox(label="タグ統計", lines=15)
        
        get_stats_btn.click(get_tag_statistics, outputs=[stats_output])
    
    gr.Markdown("""
    ---
    ### 使い方
    1. **用語管理**: PDF資料から建設業界の専門用語を自動抽出
    2. **音声文字起こし**: 会議音声を文字起こし（専門用語で自動修正）
    3. **議事録生成**: 文字起こし結果から議事録とアクションアイテムを自動生成
    4. **アクションアイテム**: 生成されたアクションアイテムの管理・追跡
    5. **タグ統計**: アクションアイテムの分類と統計情報
    """)

if __name__ == "__main__":
    app.launch(share=True)