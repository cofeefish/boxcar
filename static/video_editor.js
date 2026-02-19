////////////////////////////////////////////////////////////////////////////////////////////////////
//math functions
function round(num, places) {
    return (Math.round(num*(10**places))/(10**places))
}
function clamp(min, max, num) {
    if (num < min) {return min}
    if (num > max) {return max}
    return num
}
function distance(x1,y1,x2,y2) {
    const x_dist = x2-x1
    const y_dist = y2-y1
    return Math.sqrt(  x_dist**2 + y_dist**2 )
}
let video_edit_needed_bool = false;
function video_edit_needed() {
    if (video_edit_needed_bool) { return }
    video_edit_needed_bool = true;
    const video_edit_input = document.getElementById("video_edit_input");
    video_edit_input.value = "true";
}
function inBBox(cx,cy,sx,sy,sw,sh){
    const in_x = sx <= cx && cx <= (sw+sx)
    const in_y = sy <= cy && cy <= (sh+sy)
    const bool = in_x && in_y
    //console.log(cx,cy,sx,sy,sw,sh,bool)
    return bool;
}
// Source - https://stackoverflow.com/a/53914092
// Posted by TechWisdom, modified by community. See post 'Timeline' for change history
// Retrieved 2026-01-31, License - CC BY-SA 4.0
class ClassWatcher {

        constructor(targetNode, classToWatch, classAddedCallback, classRemovedCallback) {
            this.targetNode = targetNode
            this.classToWatch = classToWatch
            this.classAddedCallback = classAddedCallback
            this.classRemovedCallback = classRemovedCallback
            this.observer = null
            this.lastClassState = targetNode.classList.contains(this.classToWatch)

            this.init()
        }

        init() {
            this.observer = new MutationObserver(this.mutationCallback)
            this.observe()
        }

        observe() {
            this.observer.observe(this.targetNode, { attributes: true })
        }

        disconnect() {
            this.observer.disconnect()
        }

        mutationCallback = mutationsList => {
            for(let mutation of mutationsList) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    let currentClassState = mutation.target.classList.contains(this.classToWatch)
                    if(this.lastClassState !== currentClassState) {
                        this.lastClassState = currentClassState
                        if(currentClassState) {
                            this.classAddedCallback()
                        }
                        else {
                            this.classRemovedCallback()
                        }
                    }
                }
            }
        }
}
//////////////
function ensureAudioProcessing() {
        if (audioCtx !== null) { return }
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        try {
            audioSrc = audioCtx.createMediaElementSource(video);
        } catch (e) {
            console.error('Unable to create MediaElementSource from video element', e);
            return;
        }
        // create splitter and per-channel analysers
        channelSplitter = audioCtx.createChannelSplitter(2);
        analyserL = audioCtx.createAnalyser();
        analyserR = audioCtx.createAnalyser();
        analyserL.fftSize = 2048;
        analyserR.fftSize = 2048;
        analyserL.smoothingTimeConstant = 0.8;
        analyserR.smoothingTimeConstant = 0.8;
        analyserDataArrayL = new Float32Array(analyserL.fftSize);
        analyserDataArrayR = new Float32Array(analyserR.fftSize);

        // create gain node and connections: source -> gain -> splitter/destination
        gainNode = audioCtx.createGain();
        // set initial gain from slider (dB -> linear) if slider exists
        const initialGainDb = (typeof gain_slider !== 'undefined' && gain_slider) ? Number(gain_slider.value) : 0;
        gainNode.gain.value = Math.pow(10, initialGainDb / 20);
        audioSrc.connect(gainNode);
        gainNode.connect(channelSplitter);
        gainNode.connect(audioCtx.destination);
        channelSplitter.connect(analyserL, 0);
        channelSplitter.connect(analyserR, 1);

        // start the continuous sampling loop for both channels
        let loop = () => {
            if (!analyserL || !analyserR) { return }
            analyserL.getFloatTimeDomainData(analyserDataArrayL);
            analyserR.getFloatTimeDomainData(analyserDataArrayR);
            // compute RMS L
            let sumSquaresL = 0.0;
            for (let i = 0; i < analyserDataArrayL.length; i++) {
                const v = analyserDataArrayL[i];
                sumSquaresL += v * v;
            }
            const frameRmsL = Math.sqrt(sumSquaresL / analyserDataArrayL.length);
            audioRmsBufferL.push({ t: performance.now(), rms: frameRmsL });
            // compute RMS R
            let sumSquaresR = 0.0;
            for (let i = 0; i < analyserDataArrayR.length; i++) {
                const v = analyserDataArrayR[i];
                sumSquaresR += v * v;
            }
            const frameRmsR = Math.sqrt(sumSquaresR / analyserDataArrayR.length);
            audioRmsBufferR.push({ t: performance.now(), rms: frameRmsR });

            // drop old samples
            const cutoff = performance.now() - AUDIO_AVG_WINDOW_MS;
            while (audioRmsBufferL.length && audioRmsBufferL[0].t < cutoff) { audioRmsBufferL.shift(); }
            while (audioRmsBufferR.length && audioRmsBufferR[0].t < cutoff) { audioRmsBufferR.shift(); }

            requestAnimationFrame(loop);
        };
        requestAnimationFrame(loop);

        // start the audio-meter render loop once
        if (!audioMeterLoopRunning) {
            audioMeterLoopRunning = true;
            const renderLoop = () => {
                // only draw when tab is active (keeps CPU usage low)
                if (tab_class.classList.contains('active')) {
                    audio_meter();
                }
                requestAnimationFrame(renderLoop);
            };
            requestAnimationFrame(renderLoop);
        }
}
function getAverageDb(windowMs = AUDIO_AVG_WINDOW_MS, channel = 'mono') {
        const now = performance.now();
        const cutoff = now - windowMs;
        function computeFromBuffer(buf) {
            if (!buf || buf.length === 0) { return -Infinity }
            let sum = 0.0;
            let count = 0;
            for (let i = buf.length - 1; i >= 0; i--) {
                const entry = buf[i];
                if (entry.t < cutoff) { break }
                sum += entry.rms * entry.rms;
                count += 1;
            }
            if (count === 0) { return -Infinity }
            const meanSquare = sum / count;
            const rmsAvg = Math.sqrt(meanSquare);
            if (rmsAvg <= 0) { return -Infinity }
            return 20 * Math.log10(rmsAvg);
        }

        if (channel === 'L' || channel === 'l' || channel === 'left') {
            const dbL = computeFromBuffer(audioRmsBufferL);
            peak_db_L = Math.max(peak_db_L, dbL);
            return dbL;
        }
        if (channel === 'R' || channel === 'r' || channel === 'right') {
            const dbR = computeFromBuffer(audioRmsBufferR);
            peak_db_R = Math.max(peak_db_R, dbR);
            return dbR;
        }
        // mono: combine both channels' mean-square (power average) if available
        const dbL = computeFromBuffer(audioRmsBufferL);
        const dbR = computeFromBuffer(audioRmsBufferR);
        if (!isFinite(dbL) && !isFinite(dbR)) { return -Infinity }
        if (!isFinite(dbL)) { return dbR }
        if (!isFinite(dbR)) { return dbL }
        // convert dB back to linear, average power, convert to dB
        const linL = Math.pow(10, dbL / 10);
        const linR = Math.pow(10, dbR / 10);
        peak_db_L = Math.max(peak_db_L, dbL);
        peak_db_R = Math.max(peak_db_R, dbR);
        const linAvg = (linL + linR) / 2;
        return 10 * Math.log10(linAvg);
}
function dB_to_position(dB) {
        const width = audio_meter_canvas.width-audio_meter_right_margin;
        const dB_min = -65;
        const dB_max = 0;
        const db_range = dB_max - dB_min;
        dB = clamp(dB_min, dB_max, dB);
        const pct = (dB + db_range) / db_range;
        return pct * width;
}
//
function create_timecode(seconds) {
        ms = (seconds-Math.floor(seconds))*1000;
        s = Math.floor(seconds) % 60;
        m = Math.floor(seconds/60) % 60;
        h = Math.floor(m/60) % 60;
        
        const timecode = h+":"+String(m).padStart(2,"0")+":"+String(s).padStart(2,"0")+"."+String(ms).slice(0,2).padStart(2,"0");
        return timecode
}
function from_timecode(timecode) {
        const seconds = 0
}
function marker_pos_to_time(marker_x){
        return clamp(0, video.duration, ((video.duration * (marker_x - bar_x_margin)) / (bar_width)))
}
function save_marker_times(marker_times_input=document.getElementById("marker_times_input")) {
        let marker_pos_array = marker_list.dataset.marker_pos_list.split(", ")
        marker_pos_array = marker_pos_array.map(item => item.trim()).filter(item => item !== "")
        let marker_time_array = String(marker_list.dataset.marker_times).split(", ")
        marker_time_array = marker_time_array.map(item => item.trim()).filter(item => item !== "")
        for (let index = 0; index < marker_pos_array.length; index++) {
            const marker_pos = Number(marker_pos_array[index].split('-').at(-1))
            marker_time_array[index] = String(round(marker_pos_to_time(marker_pos), 3))
        }
        marker_list.dataset.marker_times = marker_time_array.join(", ")
        marker_times_input.value = marker_time_array.join(", ")
}
function save_crop_handles(){
    let crop_x       =  Number(cropper_data.dataset.crop_x);
    let crop_y       =  Number(cropper_data.dataset.crop_y);
    let crop_width   =  Number(cropper_data.dataset.crop_width);
    let crop_height  =  Number(cropper_data.dataset.crop_height);
    //convert from rendered res to original res
    const width_factor   =  (video.videoWidth/video.clientWidth)
    const height_factor  =  (video.videoHeight/video.clientHeight)
    crop_x       =  String(crop_x*width_factor)
    crop_y       =  String(crop_y*height_factor)
    crop_width   =  String(crop_width*width_factor)
    crop_height  =  String(crop_height*height_factor)

    const cropper_input_element = document.getElementById('crop_input');
    cropper_input_element.value = crop_x + ',' + crop_y + ',' + crop_width + ',' + crop_height
}

//////////////////////////////////////////////////////////////////////////////////////////////////
// graphics
function draw_trimmer() {
        //creates a trimer from two arrays in dataset attributes of marker_list
        //...marker_times, the times of each marker in seconds
        //...marker_pos_list, the x positions of each marker in pixels
        //constants
        const trimmer_display_width = trimmer_canvas.getBoundingClientRect().width;
        const trimmer_display_height = trimmer_canvas.getBoundingClientRect().height;
        trimmer_canvas.style.width = trimmer_display_width + "px";
        trimmer_canvas.style.height = trimmer_display_height + "px";
        trimmer_canvas.width = Math.round(trimmer_display_width * scale_factor);
        trimmer_canvas.height = Math.round(trimmer_display_height * scale_factor);
        const trim_bar_height = 10*scale_factor
        bar_y_pos = trim_bar_height+font_size
        end_x = trimmer_canvas.width - bar_x_margin;
        bar_width = Math.max(0, end_x - bar_x_margin);
        //setup
        const background = window.getComputedStyle( document.body ,null).getPropertyValue('background-color');
        const ctx = trimmer_canvas.getContext('2d')
        ctx.lineCap = "round";
        ctx.fillStyle = background
        ctx.fillRect(0,0,trimmer_canvas.width,trimmer_canvas.height)
        ctx.fillStyle = foreground
        ctx.font = String(font_size) + "px Arial";

        //curr timecode
        ctx.fillText(create_timecode(video.currentTime),trimmer_canvas.width/2-(font_size*2.5),font_size);
        //end timecode
        ctx.fillText(create_timecode(video.duration),trimmer_canvas.width-(font_size*5),trimmer_canvas.height/2+font_size);
        //timeline setup
        let progress_pct = 0;
        if (video.duration && isFinite(video.duration) && video.duration > 0) {
            progress_pct = clamp(0, 1, video.currentTime / video.duration);
        }
        const watched_end_pos = bar_width * progress_pct + bar_x_margin;

        //get trim markers
        let marker_pos_array = marker_list.dataset.marker_pos_list.split(", ");
        marker_pos_array = marker_pos_array.map(item => item.trim()).filter(item => item !== "");
        if (marker_pos_array.length == 0) {
            marker_pos_array.push('0-0');
            marker_pos_array.push("1-"+String(bar_x_margin));
            marker_pos_array.push("2-"+String(end_x));
        }
        marker_list.dataset.marker_pos_list = marker_pos_array.join(", ");
        //also add times
        let marker_time_array = marker_list.dataset.marker_times.split(", ");
        marker_time_array = marker_time_array.map(item => item.trim()).filter(item => item !== "");
        if (marker_time_array.length == 0) {
            marker_time_array.push("0");
            marker_time_array.push(String(round(marker_pos_to_time(bar_x_margin),3)));
            marker_time_array.push(String(round(marker_pos_to_time(end_x),3)));
        }
        marker_list.dataset.marker_times = marker_time_array.join(", ");

        //draw each segment
        for (let index = 0; index < marker_pos_array.length; index++) {
            //get marker pos
            const marker = Number(marker_pos_array[index].split('-').at(-1));
            const marker_pos = clamp(bar_x_margin, end_x, marker)

            let next_pos = end_x
            if (index+1 < marker_pos_array.length) {
                const next_marker = Number(marker_pos_array[index+1])
            }
            //console.log(marker_pos, next_pos)

            //color timeline
            ctx.lineWidth = trim_bar_height;
            //unwatched
            //if index is even it is marked out
            if (index%2==0) {ctx.strokeStyle = unwatched_out;}
            else {ctx.strokeStyle = unwatched_in;}
            ctx.beginPath();
            ctx.moveTo(marker_pos, bar_y_pos);
            ctx.lineTo(next_pos, bar_y_pos);
            ctx.closePath();
            ctx.stroke();
            //watched
            if (index%2==0) {ctx.strokeStyle = watched_out;}
            else {ctx.strokeStyle = watched_in;}
            const watched_start_pos = marker_pos
            const seg_watched_end_pos = clamp(marker_pos, next_pos, watched_end_pos)
            //console.log(marker_pos, next_pos, watched_end_pos, "->", seg_watched_end_pos)
            ctx.beginPath();
            ctx.moveTo(watched_start_pos, bar_y_pos);
            ctx.lineTo(seg_watched_end_pos, bar_y_pos);
            ctx.closePath();
            ctx.stroke();

            //draw marker
            if (index == 0) { continue }
            if (index == active_marker) { ctx.strokeStyle = active_marker_color; }
            else                        { ctx.strokeStyle = foreground; }
            ctx.lineWidth = 2*scale_factor;
            ctx.beginPath();
            ctx.moveTo(marker_pos, bar_y_pos-trim_bar_height/2-2);
            ctx.lineTo(marker_pos, bar_y_pos+trim_bar_height/2)
            ctx.closePath();
            ctx.stroke();
        }
}
function audio_meter() {

        // ensure persistent audio processing is running
        ensureAudioProcessing();
        //constants
        const audio_display_width = audio_meter_canvas.getBoundingClientRect().width;
        const audio_display_height = audio_meter_canvas.getBoundingClientRect().height;
        audio_meter_canvas.style.width = audio_display_width + "px";
        audio_meter_canvas.style.height = audio_display_height + "px";
        audio_meter_canvas.width = Math.round(audio_display_width * scale_factor);
        audio_meter_canvas.height = Math.round(audio_display_height * scale_factor);
        const audio_meter_height = 15*scale_factor
        const audio_meter_gap_height = 5*scale_factor
        //setup
        const background = window.getComputedStyle( document.body ,null).getPropertyValue('background-color');
        const ctx = audio_meter_canvas.getContext('2d')
        ctx.lineCap = "round";
        ctx.fillStyle = background
        ctx.fillRect(0,0,audio_meter_canvas.width,audio_meter_canvas.height)
        ctx.fillStyle = foreground
        ctx.font = String(font_size) + "px Arial";
        //audio meter background
        const green_pos_left = 0;
        const green_pos_right = dB_to_position(meter_green_max);
        const yellow_pos_left = green_pos_right;
        const yellow_pos_right = dB_to_position(meter_yellow_max);
        const red_pos_left = yellow_pos_right;
        const red_pos_right = audio_meter_canvas.width-audio_meter_right_margin;
        
        const real_meter_height = audio_meter_height*2+audio_meter_gap_height;
        
        ctx.fillStyle = meter_bg_green;
        ctx.fillRect(green_pos_left,0,green_pos_right,real_meter_height);
        ctx.fillStyle = meter_bg_yellow;
        ctx.fillRect(yellow_pos_left,0,yellow_pos_right-yellow_pos_left,real_meter_height);
        ctx.fillStyle = meter_bg_red;
        ctx.fillRect(red_pos_left,0,red_pos_right-red_pos_left,real_meter_height);
        // draw current averaged dB (over last ~100ms) per channel (stereo)
        const avgdbL = getAverageDb(AUDIO_AVG_WINDOW_MS, 'L');
        const avgdbR = getAverageDb(AUDIO_AVG_WINDOW_MS, 'R');

        // top = left channel, bottom = right channel
        const topY = 0;
        const topH = audio_meter_height;
        const bottomY = audio_meter_height + audio_meter_gap_height;
        const bottomH = audio_meter_height;

        // helper to draw channel bar given db value and y position
        function drawChannelBar(dbVal, y, h) {
            let green_db = clamp(-200, meter_green_max, dbVal);
            let yellow_db = clamp(-200, meter_yellow_max, dbVal);
            let red_db = clamp(-200, 0, dbVal);
            // red (lowest threshold first so layers overlap correctly)
            ctx.fillStyle = meter_fg_red;
            const red_pos = dB_to_position(red_db);
            ctx.fillRect(0, y, red_pos, h);
            ctx.fillStyle = meter_fg_yellow;
            const yellow_pos = dB_to_position(yellow_db);
            ctx.fillRect(0, y, yellow_pos, h);
            ctx.fillStyle = meter_fg_green;
            const green_pos = dB_to_position(green_db);
            ctx.fillRect(0, y, green_pos, h);
        }

        drawChannelBar(avgdbL, topY, topH);
        drawChannelBar(avgdbR, bottomY-audio_meter_gap_height, bottomH);
        // draw peak indicators
        const peakPosL = dB_to_position(peak_db_L);
        const peakPosR = dB_to_position(peak_db_R);
        ctx.fillStyle = foreground;
        ctx.fillRect(peakPosL-1, topY, 2, topH);
        ctx.fillRect(peakPosR-1, bottomY-audio_meter_gap_height, 2, bottomH);
        // draw background between L and R channels
        ctx.fillStyle = background;
        ctx.fillRect(0, bottomY/2, audio_meter_canvas.width, audio_meter_gap_height);
        // draw dB text
        ctx.fillStyle = foreground;
        const text_width = audio_meter_canvas.width - audio_meter_right_margin + 2;
        ctx.fillText("L: " + (isFinite(avgdbL) ? round(avgdbL, 0) + " dB" : "-∞ dB"), text_width, audio_meter_canvas.height/2 - 2);
        ctx.fillText("R: " + (isFinite(avgdbR) ? round(avgdbR, 0) + " dB" : "-∞ dB"), text_width, audio_meter_canvas.height - 2);


}
function draw_cropper() {
    //setup
    media_canvas.style.width = (video.clientWidth+2*cropper_handle_width) + "px";
    media_canvas.style.height = (video.clientHeight+2*cropper_handle_width) + "px";
    const cropper_display_width = media_canvas.getBoundingClientRect().width;
    const cropper_display_height = media_canvas.getBoundingClientRect().height;
    media_canvas.width = Math.round(cropper_display_width * scale_factor);
    media_canvas.height = Math.round(cropper_display_height * scale_factor);
    media_canvas.style.top = (video.offsetTop-cropper_handle_width) + "px";
    media_canvas.style.left = (video.offsetLeft-cropper_handle_width) + "px";
    //get data
    var crop_x = Number(cropper_data.dataset.crop_x);
    var crop_y = Number(cropper_data.dataset.crop_y);
    var crop_width = Number(cropper_data.dataset.crop_width);
    var crop_height = Number(cropper_data.dataset.crop_height);
    if (crop_height == Infinity) {
        cropper_data.dataset.crop_x = crop_x = 0
        cropper_data.dataset.crop_y = crop_y = 0
        cropper_data.dataset.crop_width = crop_width = video.clientWidth;
        cropper_data.dataset.crop_height = crop_height = video.clientHeight;
    }
    //draw
    const ctx = media_canvas.getContext('2d');
    ctx.fillStyle = "#ffffff";
    
    //draw border
    ctx.fillRect(crop_x, crop_y, crop_width, cropper_handle_width);
    ctx.fillRect(crop_x+crop_width, crop_y, cropper_handle_width, crop_height);
    ctx.fillRect(crop_x, crop_y+crop_height, crop_width+cropper_handle_width, cropper_handle_width);
    ctx.fillRect(crop_x, crop_y, cropper_handle_width, crop_height);
}
///////////////////////////////////////////////////////////////////////////////////////////////
//video trimmer consts
const trimmer_canvas = document.getElementById('video-trimmer');
const video = document.getElementById("video");
const tab_class = document.getElementById("tab-selector-2");
const foreground = "#000000";
const active_marker_color = "#b04040";
const unwatched_in = "#7f7f7f";
const unwatched_out = "#2f2f2f";
const watched_in = "#bfbfff";
const watched_out = "#6f6faf";
const bar_x_margin = 15;
const scale_factor = 1; //for high-DPI displays
const font_size = 12*scale_factor;
var bar_y_pos = 0;
var active_marker = -1;
var end_x = -1;
var bar_width = -1;
//audio meter consts
const audio_meter_canvas = document.getElementById('audio-meter-canvas');
const gain_slider = document.getElementById("gain-slider");
const gain_value = document.getElementById("gain-value");
const audio_meter_right_margin = 55*scale_factor;
const meter_bg_green = "#008000";
const meter_bg_yellow = "#806000";
const meter_bg_red = "#800000";
const meter_fg_green = "#00d000";
const meter_fg_yellow = "#e0b000";
const meter_fg_red = "#e00000";
const meter_green_max = -20 //in DB
const meter_yellow_max = -9 //in DB
// audio processing (persistent across frames)
let audioCtx = null;
let audioSrc = null;
let channelSplitter = null;
let analyserL = null;
let analyserR = null;
let analyserDataArrayL = null;
let analyserDataArrayR = null;
let audioRmsBufferL = []; // {t: timestamp_ms, rms: value}
let audioRmsBufferR = []; // {t: timestamp_ms, rms: value}
let audioMeterLoopRunning = false;
let gainNode = null;
const AUDIO_AVG_WINDOW_MS = 200; // averaging window for audio meter in ms
let peak_db_L = -Infinity;
let peak_db_R = -Infinity;
//cropper
const media_canvas = document.getElementById("media-canvas");
const cropper_data = document.getElementById("crop-data");
var active_cropper_handle = -1;
const handles = document.querySelectorAll('.crop-handle');
const cropper_handle_width = 2;
//runtime
var first_load = true;
window.onload  = function() {
    //initial draw
    let listenter = new ClassWatcher(tab_class, 'active', initialize_trimmer, function() {});
    function initialize_trimmer() {
        draw_trimmer()
        audio_meter();
        draw_cropper()
        save_marker_times();
    };
    //redraw
    video.addEventListener("timeupdate", () => {
        if (tab_class.classList.contains('active')==true) {
            draw_trimmer();
            audio_meter();
        }
    });
    //marker click
    trimmer_canvas.addEventListener('click', function(event) {
        if (active_marker != -1) {
            active_marker = -1
            return;
        }
        const rel_x = (event.offsetX)*scale_factor;
        const rel_y = (event.offsetY)*scale_factor;
        //test distance of click to every marker
        let marker_strings = marker_list.dataset.marker_pos_list.split(", ");
        marker_strings = marker_strings.map(item => item.trim()).filter(item => item !== "");
        for (let index = 1; index < marker_strings.length; index++) {
            const marker_string = marker_strings[index];
            const marker_pos = Number(marker_string.split('-').at(-1));
            if (distance(rel_x,rel_y,marker_pos,bar_y_pos)<20) {
                active_marker = clamp(-1, marker_strings.length, index);
                break
            }
        }
        draw_trimmer()
    });
    //mouse move
    document.body.onpointermove = event => {
        if (active_cropper_handle != -1) {
            //maybe switch to element based handles / make new controls
            //check if mouse is outside canvas
            if (! document.getElementById('media-canvas').matches(':hover')) {return;}
            const rel_x = event.offsetX
            const rel_y = event.offsetY

            video_edit_needed();
            let crop_x = Number(cropper_data.dataset.crop_x);
            let crop_y = Number(cropper_data.dataset.crop_y);
            let crop_width = Number(cropper_data.dataset.crop_width);
            let crop_height = Number(cropper_data.dataset.crop_height);

            switch (active_cropper_handle) {
                case 0:
                    cropper_data.dataset.crop_height = crop_height = crop_height + crop_y - rel_y;
                    cropper_data.dataset.crop_y = crop_y = rel_y;

                    break;
                case 1:
                    cropper_data.dataset.crop_width = crop_width = rel_x - crop_x;
                    break;
                case 2:
                    cropper_data.dataset.crop_height = crop_height = rel_y - crop_y;
                    break;
                case 3:
                    cropper_data.dataset.crop_width = crop_width = crop_width + crop_x - rel_x;
                    cropper_data.dataset.crop_x = crop_x = rel_x;
                    break;
            
                default:
                    break;
            }

            //console.log(crop_x, crop_y, crop_height, crop_width)
            draw_cropper()
            save_crop_handles()

        }
        if (active_marker != -1) {
            video_edit_needed();
            //get markers
            let marker_pos_array = marker_list.dataset.marker_pos_list.split(", ");
            marker_pos_array = marker_pos_array.map(item => item.trim()).filter(item => item !== "")
            //get marker_pos
            const rel_x = (event.clientX-trimmer_canvas.offsetLeft)*scale_factor;
            const marker_x = clamp(bar_x_margin,end_x,rel_x)
            //set markers
            marker_pos_array[active_marker]  = String(active_marker) + "-" + String(marker_x)
            marker_list.dataset.marker_pos_list = marker_pos_array.join(", ")
            save_marker_times()
            //redraw
            draw_trimmer()
        }
    }
    //gain move
    gain_slider.addEventListener('input', function() {
            video_edit_needed();
            const gain_db = Number(gain_slider.value);
            gain_value.textContent = gain_db + " dB";
            const gain_linear = Math.pow(10, gain_db / 20);
            document.getElementById("audio-data").dataset.gain = String(gain_linear);
            // if gainNode exists, apply immediately
            if (gainNode && gainNode.gain) {
                gainNode.gain.value = gain_linear;
            }
    });
    //cropper handle click
    media_canvas.addEventListener('click', function (event) {
        if (active_cropper_handle != -1) {
            active_cropper_handle = -1; //ordered clockwise, 0 is top
            return
        }
        const rel_x = event.offsetX
        const rel_y = event.offsetY
        //check if/which handle click was over
        let crop_x = Number(cropper_data.dataset.crop_x);
        let crop_y = Number(cropper_data.dataset.crop_y);
        let crop_width = Number(cropper_data.dataset.crop_width);
        let crop_height = Number(cropper_data.dataset.crop_height);
        if (crop_height == Infinity) {
            crop_x = 0
            crop_y = 0
            crop_width = video.clientWidth;
            crop_height = video.clientHeight;
        }
        //top
        
        if      (inBBox(rel_x, rel_y, crop_x, crop_y, crop_width, cropper_handle_width)) {active_cropper_handle = 0;}
        else if (inBBox(rel_x, rel_y, crop_x+crop_width, crop_y, cropper_handle_width, crop_height)) {active_cropper_handle = 1;}
        else if (inBBox(rel_x, rel_y, crop_x, crop_y+crop_height, crop_width, cropper_handle_width)) {active_cropper_handle=2;}
        else if (inBBox(rel_x, rel_y, crop_x, crop_y, cropper_handle_width, crop_height)) {active_cropper_handle=3;}

        const over_handle = (active_cropper_handle != -1);
        if (!over_handle) {
            if (video.paused) {
              video.play();
            } else {
              video.pause();
            }
        }
        console.log(active_cropper_handle)

    });
    // update canvases on resize (debounced)
    let resizeTimer;
    window.addEventListener('resize', () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
                if (tab_class.classList.contains('active')) {
                    draw_trimmer();
                    audio_meter();
                    draw_cropper()
                }
            }, 150);
    });
}

