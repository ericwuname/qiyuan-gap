var _empData=[],_empPage=0,_empPageSize=10;
function renderEmpPage(){
  var d=_empData,p=_empPage,s=_empPageSize,t=d.length,ps=Math.ceil(t/s),st=p*s,sl=d.slice(st,st+s);
  var tb=document.getElementById("hr-detail-table");tb.innerHTML="";
  sl.forEach(function(e){
    var tB=e.tier?("<span class=badge style=background:"+(tierColors[e.tier]||"#333")+"20;color:"+(tierColors[e.tier]||"#666")+">"+e.tier+"</span>"):"-";
    var sB=(e.capability_score||0)>=7?("<span class='badge badge-green'>"+e.capability_score.toFixed(1)+"</span>"):
           (e.capability_score||0)>=5?("<span class='badge badge-yellow'>"+e.capability_score.toFixed(1)+"</span>"):
           ("<span class=badge>"+(e.capability_score||0).toFixed(1)+"</span>");
    tb.innerHTML+="<tr><td style=font-size:11px;color:#556677>"+e.id+"</td><td>"+e.name+"</td><td>"+e.role+"</td><td>"+tB+"</td><td style=font-size:11px;color:#8899aa>"+ (e.department||"-") +"</td><td>"+sB+"</td><td>"+(e.status||"active")+"</td><td style=font-size:11px;color:#556677>"+ (e.last_assessment||"-") +"</td></tr>";
  });
  document.getElementById("emp-page-info").textContent=(st+1)+"-"+Math.min(st+s,t)+" / "+t;
  var pg=document.getElementById("emp-pagination");
  pg.innerHTML="<button "+(p===0?"disabled":"")+" onclick=window._empPage=0;renderEmpPage()>|..|</button><button "+(p===0?"disabled":"")+" onclick=window._empPage--;renderEmpPage()>..</button><span class=page-info>"+(p+1)+"/"+ps+"</span><button "+(p>=ps-1?"disabled":"")+" onclick=window._empPage++;renderEmpPage()>..</button><button "+(p>=ps-1?"disabled":"")+" onclick=window._empPage="+(ps-1)+";renderEmpPage()>..|</button>";
}

var _skillData=[],_skillPage=0,_skillPageSize=10;
function renderSkillPage(){
  var d=_skillData,p=_skillPage,s=_skillPageSize,t=d.length,ps=Math.ceil(t/s),st=p*s,sl=d.slice(st,st+s);
  var tb=document.getElementById("hr-skills-table");tb.innerHTML="";
  sl.forEach(function(sk){
    var desc=sk.description||"-";if(desc.length>100)desc=desc.slice(0,100)+"...";
    var cB=sk.category?("<span class=badge style=background:#1a3a4a;color:#66b1ff>"+sk.category+"</span>"):"-";
    tb.innerHTML+="<tr><td>"+sk.skill_name+"</td><td>"+ (sk.owner||"-") +"</td><td>"+cB+"</td><td style=font-size:12px;color:#ccc>"+desc+"</td><td style=font-size:11px;color:#556677>"+ (sk.last_updated||"-") +"</td></tr>";
  });
  document.getElementById("skill-page-info").textContent=(st+1)+"-"+Math.min(st+s,t)+" / "+t;
  var pg=document.getElementById("skill-pagination");
  pg.innerHTML="<button "+(p===0?"disabled":"")+" onclick=window._skillPage=0;renderSkillPage()>|..|</button><button "+(p===0?"disabled":"")+" onclick=window._skillPage--;renderSkillPage()>..</button><span class=page-info>"+(p+1)+"/"+ps+"</span><button "+(p>=ps-1?"disabled":"")+" onclick=window._skillPage++;renderSkillPage()>..</button><button "+(p>=ps-1?"disabled":"")+" onclick=window._skillPage="+(ps-1)+";renderSkillPage()>..|</button>";
}