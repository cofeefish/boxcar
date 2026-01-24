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

//////////////////////////////////////////////////////////////////////////////////////////////////
// graphics
function draw_trimmer() {
    //console.log('creating timmer')
    //constants
    canvas.width = canvas.clientWidth*scale_factor
    canvas.height = canvas.clientHeight*scale_factor
    const trim_bar_height = 10*scale_factor
    bar_y_pos = trim_bar_height+font_size
    end_x = canvas.width - bar_x_margin;
    bar_width = Math.max(0, end_x - bar_x_margin);
    //setup
    const background = window.getComputedStyle( document.body ,null).getPropertyValue('background-color');
    const ctx = canvas.getContext('2d')
    canvas.width = canvas.clientWidth*scale_factor
    canvas.height = canvas.clientHeight*scale_factor
    ctx.lineCap = "round";
    ctx.fillStyle = background
    ctx.fillRect(0,0,canvas.width,canvas.height)
    ctx.fillStyle = foreground
    ctx.font = String(font_size) + "px Arial";

    //curr timecode
    ctx.fillText(create_timecode(video.currentTime),canvas.width/2-(font_size*2.5),font_size);
    //end timecode
    ctx.fillText(create_timecode(video.duration),canvas.width-(font_size*5),canvas.height/2+font_size);
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
function audio_meter() {}

///////////////////////////////////////////////////////////////////////////////////////////////
//constants - elements
const canvas = document.getElementById('video-trimmer')
const video = document.getElementById("video")
var tab_class = document.getElementById("tab-selector-2").classList
const marker_list = document.getElementById('segment_list')
//constants - colors
const foreground = "#000000";
const active_marker_color = "#b04040";
const unwatched_in = "#7f7f7f";
const unwatched_out = "#2f2f2f";
const watched_in = "#bfbfff";
const watched_out = "#6f6faf";
//constants - other
const bar_x_margin = 15
const scale_factor = 2;
const font_size = 12*scale_factor;
var bar_y_pos = 0
var active_marker = -1
var end_x = -1
var bar_width = -1
//runtime
window.onload  = function() {
    //redraw
    video.addEventListener("timeupdate", () => {
        if (tab_class.contains('active')==true) {
            draw_trimmer()
            audio_meter()
        }
    });

    //marker click
    canvas.addEventListener('click', function(event) {
        active_marker = -1
        const rel_x = (event.clientX-canvas.offsetLeft)*scale_factor;
        const rel_y = (event.clientY-canvas.offsetTop)*scale_factor;

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

    //marker move
    document.body.onpointermove = event => {
        if (active_marker == -1) { return }

        //get markers
        let marker_time_array = String(marker_list.dataset.marker_times).split(", ")
        marker_time_array = marker_time_array.map(item => item.trim()).filter(item => item !== "")
        let marker_pos_array = marker_list.dataset.marker_pos_list.split(", ");
        marker_pos_array = marker_pos_array.map(item => item.trim()).filter(item => item !== "")
        //get marker_pos
        const rel_x = (event.clientX-canvas.offsetLeft)*scale_factor;
        const marker_x = clamp(bar_x_margin,end_x,rel_x)
        const marker_time = marker_pos_to_time(marker_x)
        //set markers
        marker_time_array[active_marker] = round(marker_time,3)
        marker_pos_array[active_marker]  = String(active_marker) + "-" + String(marker_x)
        marker_list.dataset.marker_times = marker_time_array.join(", ")
        marker_list.dataset.marker_pos_list = marker_pos_array.join(", ")
        marker_times_input.value = marker_time_array.join(", ")
        //redraw
        draw_trimmer()
    }
}
