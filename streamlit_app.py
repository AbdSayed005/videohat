import streamlit as st
import yt_dlp
import requests
from PIL import Image
from io import BytesIO
import os
import time
import humanize
from datetime import datetime

# 🔹 إعداد المجلدات
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# 🔹 تهيئة حالة التطبيق
if 'selected_videos' not in st.session_state:
    st.session_state.selected_videos = []
if 'download_history' not in st.session_state:
    st.session_state.download_history = []
if 'selected_formats' not in st.session_state:
    st.session_state.selected_formats = {}

# 🔹 تكوين yt-dlp
YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,
    'ignoreerrors': True,
    'no_color': True,
    'retries': 5,
    'fragment_retries': 5,
    'socket_timeout': 30,
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'merge_output_format': 'mp4',
    'postprocessors': [{
        'key': 'FFmpegVideoConvertor',
        'preferedformat': 'mp4',
    }, {
        'key': 'FFmpegMetadata',
        'add_metadata': True,
    }],
}

def calculate_total_size(videos, selected_formats=None):
    """حساب الحجم الإجمالي للفيديوهات المحددة"""
    total_size = 0
    for video in videos:
        if selected_formats and video['url'] in selected_formats:
            format_id = selected_formats[video['url']]
            for fmt in video['formats']:
                if fmt['format_id'] == format_id:
                    total_size += fmt['filesize']
                    break
        else:
            if video['formats']:
                total_size += video['formats'][0]['filesize']
    return total_size

@st.cache_data(ttl=3600)
def get_video_info(url):
    """استخراج معلومات الفيديو مع معالجة محسنة للأخطاء"""
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                st.error("❌ لم يتم العثور على معلومات الفيديو")
                return None
                
            # معالجة قوائم التشغيل
            if 'entries' in info:
                videos = []
                for entry in info['entries']:
                    if entry:
                        video_data = extract_video_data(entry['url'])
                        if video_data:
                            videos.append(video_data)
                return videos
            
            # معالجة فيديو منفرد
            return [extract_video_data(url)]
            
    except Exception as e:
        st.error(f"❌ خطأ في استخراج المعلومات: {str(e)}")
        return None

def extract_video_data(url):
    """استخراج بيانات فيديو واحد"""
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None

            formats = []
            # تصفية الصيغ للحصول على الفيديوهات مع الصوت
            for f in info.get('formats', []):
                if f.get('acodec') != 'none' and f.get('vcodec') != 'none':
                    format_info = {
                        'format_id': f['format_id'],
                        'ext': f['ext'],
                        'quality': f.get('format_note', 'N/A'),
                        'resolution': f.get('resolution', 'N/A'),
                        'filesize': f.get('filesize', 0),
                        'filesize_readable': humanize.naturalsize(f.get('filesize', 0)),
                        'fps': f.get('fps', 0),
                        'acodec': f.get('acodec', 'N/A'),
                        'vcodec': f.get('vcodec', 'N/A')
                    }
                    formats.append(format_info)

            # إذا لم نجد صيغ مع صوت، نضيف أفضل صيغة متاحة
            if not formats:
                best_format = info.get('format_id', 'best')
                formats.append({
                    'format_id': best_format,
                    'ext': 'mp4',
                    'quality': 'أفضل جودة متاحة',
                    'resolution': 'auto',
                    'filesize': 0,
                    'filesize_readable': 'غير معروف',
                    'fps': 0
                })

            return {
                'title': info.get('title', 'بدون عنوان'),
                'url': url,
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration', 0),
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'formats': sorted(formats, key=lambda x: x['filesize'], reverse=True)
            }
    except Exception as e:
        st.warning(f"⚠️ تعذر استخراج بيانات الفيديو: {str(e)}")
        return None

def download_video(url, format_id, progress_bar=None):
    """تحميل الفيديو مع عرض التقدم"""
    try:
        filename = f"video_{int(time.time())}.mp4"
        output_path = os.path.join(DOWNLOAD_FOLDER, filename)
        
        options = {
            **YDL_OPTS,
            'format': f'{format_id}+bestaudio[ext=m4a]/best',
            'outtmpl': output_path,
            'progress_hooks': [
                lambda d: update_progress(d, progress_bar)
            ] if progress_bar else [],
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }]
        }
        
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])
            return output_path
    except Exception as e:
        st.error(f"❌ خطأ في التحميل: {str(e)}")
        return None

def update_progress(d, progress_bar):
    """تحديث شريط التقدم"""
    if d['status'] == 'downloading':
        total = d.get('total_bytes', 0)
        downloaded = d.get('downloaded_bytes', 0)
        if total > 0:
            progress = (downloaded / total)
            progress_bar.progress(progress)
# 🔹 واجهة المستخدم
st.set_page_config(
    page_title="Video Downloader",
    page_icon="🎥",
    layout="wide"
)

# التصميم
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #FF0050;
        color: white;
        border-radius: 10px;
        padding: 0.5rem;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #CC0040;
        transform: translateY(-2px);
    }
    .video-info {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .total-size {
        padding: 1rem;
        background-color: #e9ecef;
        border-radius: 10px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("⚙️ الإعدادات")
    
    # خيارات العرض
    st.subheader("🎨 خيارات العرض")
    show_thumbnails = st.toggle("عرض الصور المصغرة", value=True)
    
    # إحصائيات
    st.subheader("📊 إحصائيات")
    st.write(f"عدد التحميلات: {len(st.session_state.download_history)}")
    
    # تنظيف المجلد
    if st.button("🗑️ تنظيف مجلد التحميلات"):
        try:
            for file in os.listdir(DOWNLOAD_FOLDER):
                file_path = os.path.join(DOWNLOAD_FOLDER, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            st.success("✅ تم تنظيف المجلد بنجاح")
        except Exception as e:
            st.error(f"❌ خطأ في التنظيف: {str(e)}")

# الواجهة الرئيسية
st.title("🎥 تحميل الفيديوهات")
st.markdown("##### قم بتحميل الفيديوهات من YouTube و TikTok")

# إدخال الرابط
url = st.text_input("🔗 أدخل رابط الفيديو أو قائمة التشغيل:")

if url:
    with st.spinner("⏳ جاري تحليل الرابط..."):
        videos = get_video_info(url)
        
        if videos:
            st.success(f"✅ تم العثور على {len(videos)} فيديو")
            
            # زر تحديد الكل
            select_all = st.checkbox("✅ تحديد الكل")
            
            # حساب وعرض الحجم الإجمالي
            if select_all or st.session_state.selected_videos:
                total_size = calculate_total_size(
                    videos if select_all else st.session_state.selected_videos,
                    st.session_state.selected_formats
                )
                st.markdown(f"""
                <div class='total-size'>
                    📦 الحجم الإجمالي: {humanize.naturalsize(total_size)}
                </div>
                """, unsafe_allow_html=True)

            # أزرار التحكم الرئيسية
            control_cols = st.columns([1, 1])
            with control_cols[0]:
                if st.button("⬇️ تحميل المحدد", use_container_width=True):
                    for video in st.session_state.selected_videos:
                        progress_bar = st.progress(0)
                        format_id = st.session_state.selected_formats.get(
                            video['url'],
                            video['formats'][0]['format_id']
                        )
                        file_path = download_video(video['url'], format_id, progress_bar)
                        if file_path and os.path.exists(file_path):
                            with open(file_path, "rb") as file:
                                st.download_button(
                                    label=f"💾 حفظ {video['title']}",
                                    data=file,
                                    file_name=os.path.basename(file_path),
                                    mime="video/mp4",
                                    use_container_width=True
                                )

            with control_cols[1]:
                if st.button("📥 تحميل الكل", use_container_width=True):
                    for video in videos:
                        progress_bar = st.progress(0)
                        format_id = st.session_state.selected_formats.get(
                            video['url'],
                            video['formats'][0]['format_id']
                        )
                        file_path = download_video(video['url'], format_id, progress_bar)
                        if file_path and os.path.exists(file_path):
                            with open(file_path, "rb") as file:
                                st.download_button(
                                    label=f"💾 حفظ {video['title']}",
                                    data=file,
                                    file_name=os.path.basename(file_path),
                                    mime="video/mp4",
                                    use_container_width=True
                                )

            # عرض الفيديوهات
            for i, video in enumerate(videos):
                if video:
                    with st.container():
                        st.markdown("---")
                        cols = st.columns([1, 2])
                        
                        # عرض الصورة المصغرة
                        with cols[0]:
                            if show_thumbnails and video['thumbnail']:
                                try:
                                    response = requests.get(video['thumbnail'])
                                    img = Image.open(BytesIO(response.content))
                                    st.image(img, use_container_width=True)
                                except:
                                    st.warning("⚠️ تعذر تحميل الصورة المصغرة")
                        
                        # معلومات الفيديو
                        with cols[1]:
                            # مربع اختيار التحديد
                            is_selected = st.checkbox(
                                "تحديد للتحميل",
                                key=f"select_{video['url']}",
                                value=select_all
                            )
                            if is_selected and video not in st.session_state.selected_videos:
                                st.session_state.selected_videos.append(video)
                            elif not is_selected and video in st.session_state.selected_videos:
                                st.session_state.selected_videos.remove(video)
                            
                            st.subheader(video['title'])
                            
                            # إحصائيات
                            stats_cols = st.columns(3)
                            with stats_cols[0]:
                                st.metric("المشاهدات", humanize.intword(video['view_count']))
                            with stats_cols[1]:
                                st.metric("الإعجابات", humanize.intword(video['like_count']))
                            with stats_cols[2]:
                                duration = time.strftime('%H:%M:%S', time.gmtime(video['duration']))
                                st.metric("المدة", duration)
                            
                            # اختيار الجودة
                            if video['formats']:
                                format_options = {
                                    f"{f['quality']} - {f['resolution']} ({f['filesize_readable']})": f['format_id']
                                    for f in video['formats']
                                }
                                
                                selected_format = st.selectbox(
                                    "📊 اختر الجودة:",
                                    options=list(format_options.keys()),
                                    key=f"quality_{video['url']}"
                                )
                                # حفظ الجودة المحددة
                                st.session_state.selected_formats[video['url']] = format_options[selected_format]
                                
                                # زر تحميل فردي
                                if st.button("⬇️ تحميل", key=f"download_{video['url']}", use_container_width=True):
                                    progress_bar = st.progress(0)
                                    file_path = download_video(
                                        video['url'],
                                        format_options[selected_format],
                                        progress_bar
                                    )
                                    if file_path and os.path.exists(file_path):
                                        with open(file_path, "rb") as file:
                                            st.download_button(
                                                label="💾 حفظ الفيديو",
                                                data=file,
                                                file_name=os.path.basename(file_path),
                                                mime="video/mp4",
                                                use_container_width=True
                                            )

# Footer
st.markdown("""
<div style='text-align: center; margin-top: 2rem; padding: 1rem; color: gray;'>
    🚀 تم التطوير بواسطة <b>خباب</b> ❤️
</div>
""", unsafe_allow_html=True)            
