JsOsaDAS1.001.00bplist00�Vscript_var iTunes = Application('Music');

var track = {};
var cT = iTunes.currentTrack;
var state = iTunes.playerState()
	
if (state == 'playing') {
	track["album"] = cT.album();
	track["artist"] = cT.artist();
	track["name"] = cT.name();
	track["time"] = cT.time();
}

JSON.stringify(track);                              4jscr  ��ޭ