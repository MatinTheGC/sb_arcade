//
var nav = window.navigator.userAgent.toString().toLowerCase();
var isWin = nav.indexOf("windows") > -1 || nav.indexOf("win") > -1;
var isMSIE = nav.indexOf("msie") > -1 && nav.indexOf("opera") == -1;
var defaultPlayerParams = {menu:"false",bgcolor:"#FFFFFF",allowScriptAccess:"always"};

var flashVersion = -1;
if(isWin && isMSIE) {
	document.write( '<SCR'+'IPT LANGUAGE="VBScript">\non error resume next\nFor i = 6 to 10\n\tIf Not(IsObject(CreateObject("ShockwaveFlash.ShockwaveFlash." & i))) Then\n\tElse\n\t\t flashVersion = i\n\tEnd If\nNext\n</SCR'+'IPT>');
}
else {
	if(navigator.plugins && navigator.plugins.length) {
		var plFlash = navigator.plugins["Shockwave Flash"];
		if(plFlash!=null) {
			flashVersion = parseInt(plFlash.description.substr(15));
		}
	}
}

function createFlashPlayer (src, width, height, params, flashvars, parentId) {
	var str = "";
	if(params==null) { params={}; }
	
	if(params.name != null) params.id = params.name;
	var p={};
	for(var i in defaultPlayerParams) {p[i]=defaultPlayerParams[i];}
	for(var i in params) {p[i]=params[i];}
	
	var fv="";
	if(flashvars != null) {
		for(var i in flashvars) {fv+=i+"="+escape(flashvars[i])+"&";}
	}
	if(isWin && isMSIE) {
		/*make object*/
		if(parentId==null) { alert("An id is required for embedding the flash player in internet explorer."); return; }
		var obj = document.createElement("object");
 		var d = document.getElementById(parentId);
		d.appendChild(obj);
		obj.classid="clsid:D27CDB6E-AE6D-11cf-96B8-444553540000";
 		obj.codebase="http://download.macromedia.com/pub/shockwave/cabs/flash/swflash.cab#version=8,0,0,0";
 		obj.width=width;
 		obj.height=height;
		obj.flashVars=fv;
		if(src != null) obj.movie=src;
 		for(var i in p) {
			if(i=="__proto__")continue;
			obj[i] = p[i]; 
		}
 		return obj;
	}
	else {
		str += "<embed src=\"" + src + "\" flashVars=\"" + fv + "\" width=\"" + width + "\" height=\"" + height + "\"";
		for(var i in p) {if(i=="__proto__")continue; str += " " + i + "=\"" + p[i] + "\""; }
		str += "></embed>";
		//alert(str);
		document.write(str);
	}
}