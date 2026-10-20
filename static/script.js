document.addEventListener("DOMContentLoaded", function() {
    const videos = document.querySelectorAll('.video-container video');

    // مراقب التمرير لتشغيل الفيديو الذي في المنتصف
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            const video = entry.target;
            if (entry.isIntersecting) {
                // تشغيل الفيديو (سيعمل لأننا جعلناه مكتوم muted)
                video.play().catch(e => console.log("خطأ في التشغيل التلقائي:", e));
            } else {
                video.pause();
                video.currentTime = 0;
            }
        });
    }, { threshold: 0.6 });

    videos.forEach(video => {
        observer.observe(video);
    });
});

// دالة التشغيل/الإيقاف عند الضغط على الفيديو
function togglePlay(video) {
    if (video.paused) {
        video.play();
    } else {
        video.pause();
    }
}

// دالة تفعيل/كتم الصوت
function toggleMute(btn) {
    // إيجاد الفيديو المرتبط بهذا الزر
    const video = btn.parentElement.querySelector('video');
    const icon = btn.querySelector('i');
    
    if (video.muted) {
        video.muted = false;
        icon.classList.remove('fa-volume-xmark');
        icon.classList.add('fa-volume-high');
    } else {
        video.muted = true;
        icon.classList.remove('fa-volume-high');
        icon.classList.add('fa-volume-xmark');
    }
}
