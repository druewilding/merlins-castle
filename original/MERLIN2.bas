   15 MODE7:PROCoff:d%=24
   20 PROCinit:PROCtitle
   25 ONERRORIFERR=17THEN30ELSE4140
   30 PROCoptions:IFCH=4THEN4140
   35 IFCH=3PROCinfo:GOTO30
   37 IFCH=2PROCLOAD:IFX=0THEN30
   38 C%=-C%*(CH=2):PROCroom
   40 PROClook
   50 down=15
  100 REPEAT
  110 PROCask
  120 UNTILv$="qui"ORv$="sav":IFv$="qui"PROCshow:GOTO30
  130 *FX200,0
  132 ONERRORIFERR=17THEN30ELSE4140
  135 PROCSAVE:IFB%=1THEN190
  137 *FX200,1
  140 ONERRORGOTO170
  150 $&A00="ACCESS S."+P$:X%=0:Y%=&A:CALL&FFF7
  160 VDU28,0,24,39,15,12,26:PROCc("The file exists. Replace (Y/N)?",15,W$):PROCB(3,17,18,B$):PRINTTAB(20,20);:PROCYN:IFG<>78ANDG<>89THEN160
  165 IFG=78THEN130
  170 ONERRORIFERROR=17THEN30ELSE4140
  180 PROCSAVE2
  190 PROCshow:GOTO30
 1000 DEFPROCshow
 1010 CLS:PROCc("Today's scores",3,G$):PROCc("Best possible score: 100",8,PB$):PROCc("Best score so far: "+STR$(max),13,R$)
 1020 sc=1:PROCscore
 1030 PROCc("Your score this time: "+STR$(s%),18,G$)
 1040 IFs%>max max=s%
 1050 PROCr:ENDPROC
 1100 DEFPROCWAIT(T)
 1110 G=INKEY(100*T):ENDPROC
 1200 DEFPROCr
 1205 *FX15,1
 1210 PROCbar:PRINTTAB(26,24)W$"Press RETURN";
 1215 REPEAT:G=GET:UNTILG=13:PRINTTAB(26,24)W$"            ";
 1220 ENDPROC
 1250 DEFPROCbar
 1260 PRINTTAB(0,24)G$CHR$157;:ENDPROC
 1300 DEFPROCc(wx$,Y,COL$)
 1310 PROCb(wx$,INT((40-LEN(wx$))/2)-2,Y,COL$):ENDPROC
 1600 DEFPROCCLS(D%)
 1610 VDU28,0,23,39,D%,12,26
 1620 ENDPROC
 1700 DEFPROCoff
 1710 VDU23;11,0;0;0;0:ENDPROC
 1800 DEFPROCon
 1810 VDU23;11,255;0;0;0:ENDPROC
 2000 DEFPROCret
 2010 PROCc("Press "+R$+"RETURN",d%-1,W$)
 2020 *FX15,1
 2030 REPEAT:K$=GET$:UNTILK$=CHR$13
 2040 ENDPROC
 2050 DEFPROCRET
 2060 PROCc("Press "+R$+"RETURN"+Y$+" TWICE",d%-1,W$):GOTO2020
 2070 DEFPROCSAVE
 2080 IF?&215=255B%=0:MED$="disk":MAC$="disk drive"ELSEB%=1:MED$="tape":MAC$="recorder"
 2090 PROCname("Name of your position file?",7)
 2100 *TAPE
 2110 IFB%=1THEN2130
 2120 *DISC
 2130 PROCc("Put the new "+MED$+" in the "+MAC$+".",15,W$)
 2140 IFB%=1PROCc("Press PLAY and RECORD.",18,W$):PROCRET:GOTO2170
 2150 PROCret:ENDPROC
 2160 DEFPROCSAVE2
 2170 VDU28,0,24,39,15,12,26:PROCc("The "+P$+" file is saving.",15,W$):PRINTTAB(0,18)CHR$152:VDU28,1,18,2,18:PROCsave:VDU26
 2180 VDU28,0,24,39,15,12,26:PROCc("Your file is called"+G$+LEFT$(P$,7),15,W$)
 2190 IFB%=1PROCc("Press the STOP button",18,W$)
 2200 PROCret:ENDPROC
 2210 DEFPROCsave
 2220 ONERRORGOTO2350
 2230 *FX200,1
 2240 X=OPENOUT("S."+LEFT$(P$,7))
 2250 PRINT#X,r,C%,W
 2260 FORK%=1TONI:PRINT#X,w(K%),c(K%):NEXT
 2320 CLOSE#X:ONERRORIFERR=17THEN30ELSE4140
 2330 *FX200,0
 2340 ENDPROC
 2350 ONERRORIFERR=17THEN30ELSE4140
 2355 CLOSE#0:VDU26:ME$="Error "+STR$(ERR)
 2360 IFERR=198ME$="Disk is full"
 2370 IFERR=201ME$="Protect label on"
 2380 IFERR=191ME$="No room for file"
 2385 IFERR=190ME$="Catalogue full"
 2390 PROCCLS(15):PROCc(ME$,18,G$):PROCret
 2410 *FX200,0
 2420 PROCroom:PROClook:GOTO100
 2430 DEFPROCname(z$,l)
 2440 CLS:PROCc(z$,4,W$)
 2450 PROCB(l+3,(34-l)/2,8,B$):PRINTTAB((34-l)/2+3,10);:PROCi(45,90,l,W$,1)
 2460 P$=IN$:ENDPROC
 2470 DEFPROCYN
 2480 PROCi(65,90,1,W$,1):G=ASC(IN$)
 2490 ENDPROC
 2500 DEFPROCLOAD
 2510 IF?&215=255B%=0:MED$="disk":MAC$="disk drive"ELSEB%=1:MED$="tape":MAC$="recorder"
 2520 PROCname("Name of your position file?",7)
 2530 PROCb("Put the master "+MED$+" in the "+MAC$+".",0,15,W$)
 2540 IFB%=1PROCc("Press the PLAY button.",18,W$)
 2550 PROCret:VDU28,0,24,39,15,12,26
 2560 *TAPE
 2570 IFB%=1THEN2590
 2580 *DISC
 2590 PROCload:VDU26
 2600 IFX=0PROCc("No such file",18,G$):GOTO2630
 2610 F$="Ready.":IFB%=1F$=F$+"  Press the STOP button."
 2620 PROCc(F$,18,W$)
 2630 PROCret:ENDPROC
 2640 DEFPROCload
 2650 X=OPENUP("S."+LEFT$(P$,7)):IFX=0THEN2720
 2660 *FX200,1
 2670 ONERRORGOTO2740
 2680 PROCCLS(15):PROCc("The "+P$+" file is loading.",15,W$):PRINTTAB(0,18)CHR$152:VDU28,1,18,2,18
 2690 INPUT#X,r,C%,W
 2700 FORK%=1TONI:INPUT#X,w(K%),c(K%):NEXT
 2710 CLOSE#X:ONERRORIFERR=17THEN30ELSE4140
 2720 *FX200,0
 2730 ENDPROC
 2740 CLOSE#X:VDU26:ME$="Not a position file"
 2750 VDU28,0,24,39,15,12,26:PROCc(ME$,18,G$):PROCret
 2760 ONERRORIFERR=17THEN30ELSE4140
 2770 GOTO30
 3000 DEFPROCn(ME$)
 3005 XC=POS:YC=VPOS
 3040 PROCCLS(down+4):PROCb(ME$,0,down+4,R$):VDU7:PROCWAIT(TM)
 3060 PROCCLS(down+4):TM=KT:PRINTTAB(XC,YC);:ENDPROC
 4140 *FX 4,0
 4145 *FX 12,0
 4150 *FX202,32
 4160 MODE7:PRINT"End of program":IFCH=4ORERR=17THEN4170
 4165 REPORT:PRINT" in line ";ERL
 4170 GOTO31000
 4500 DEFPROCoptions:*FX202,32
 4502 PROCstart:FL%=0:sc=0:C%=0
 4505 CLS:PROCc("Choice Page",1,G$):PROCb("You can:",0,4,W$):*FX200,0
 4510 PROCb("A  "+W$+"start a new adventure",5,7,G$)
 4520 PROCb("B  "+W$+"load your old position",5,10,G$)
 4535 PROCb("C  "+W$+"see the notes",5,13,G$)
 4540 PROCb("D  "+W$+"stop",5,16,G$)
 4550 PROCb("Type a letter then"+G$+"RETURN",0,21,W$)
 4560 PROCB(3,32,20,G$)
 4570 PRINTTAB(35,22);:PROCi(65,68,1,W$,1)
 4580 CH=ASC(IN$)-64
 4590 FL%=1:ENDPROC
 5000 DEFPROCprint(T$,YY,col$)
 5010 REPEAT
 5020 L$=LEFT$(T$,38):T$=MID$(T$,39):G=ASC(T$):IFG=32G=135
 5030 IFG>126ORG=-1T$=MID$(T$,2):GOTO5060
 5040 L=LEN(L$)+1:REPEAT:L=L-1:G=ASC(MID$(L$,L,1)):UNTILG=32ORG>126:IFG=32G=135
 5050 T$=MID$(L$,L+1)+T$:L$=LEFT$(L$,L-1)
 5060 PROCb(L$,0,YY,col$):col$=CHR$G:YY=YY+2
 5070 UNTILG=-1
 5080 zy=YY+2:ENDPROC
 5500 DEFPROCb(A$,X,Y,cl$)
 5510 cl=ASC(cl$)-128
 5580 PRINTTAB(X,Y)DH$cl$A$TAB(X,Y+1)DH$cl$A$;
 5590 ENDPROC
 7000 DEFPROCi(LO,HI,len,col$,cap)
 7005 XX=POS-1:YY=VPOS:IN$="":LI=0:PROCon
 7010 *FX15,1
 7020 GOSUB7200:IFG=127ORG=13ORG=32THEN7020
 7025 IFcap=0ANDG>64G=G+32
 7030 IN$=CHR$(G):LI=1:PROCb(IN$,XX-1,YY-1,col$)
 7040 GOSUB7200:IFG=13THEN7300
 7060 IFG<>127THEN7100
 7070 LI=LI-1:IFLI>-1THENIN$=LEFT$(IN$,LEN(IN$)-1)
 7075 PROCb(IN$+" "+CHR$8,XX-1,YY-1,col$):IFLI=0THEN7010ELSE7040
 7100 IFG>64THENG=G+32
 7110 IN$=IN$+CHR$(G):LI=LI+1:PROCb(IN$,XX-1,YY-1,col$):GOTO7040
 7200 GC=0
 7210 G=INKEY(60):GC=GC-(LI>0):IFG=13ORG=127ORG=32THENRETURN
 7220 IFLI=lenTHEN7260
 7240 IFG>96THENG=G-32
 7250 IFG>=LOANDG<=HITHENRETURN
 7260 IFGC>20THENGC=0:TM=1:IFFL%<>0PROCoff:PROCn(" Press RETURN"):PROCon
 7270 GOTO7210
 7300 PROCoff:ENDPROC
 7500 DEFPROCB(LL,X1,Y1,col$)
 7505 BOXcol=ASC(col$)+16
 7510 PRINTTAB(X1-1,Y1);
 7520 VDUBOXcol,183,163:FORK=1TOLL:VDU163:NEXT:VDU163,235
 7530 FORJ=1TO2:PRINTTAB(X1-2,Y1+1);:VDU141BOXcol,181,32:FORK=1TOLL:VDU32:NEXT:VDUBOXcol,234
 7540 Y1=Y1+1:NEXT:PRINTTAB(X1-1,Y1+1);
 7550 VDUBOXcol,245,240:FORK=1TOLL:VDU240:NEXT:VDU240,250
 7560 ENDPROC
 8000 DEFPROCtitle
 8005 TL$="Merlin's Castle"
 8010 *FX4,1
 8015 *FX11,0
 8110 ENDPROC
 9000 DEFPROCinfo
 9005 CLS:PROCc(TL$,0,G$)
 9010 PROCb("You go out for a walk on a warm, sunny",0,3,W$):PROCb("day.  You become tired and you fall",0,5,W$):PROCb("asleep on a grassy bank. When you wake",0,7,W$):PROCb("up you are in a magic land where there",0,9,W$)
 9015 PROCb("are treasures to be found.",0,11,W$)
 9020 PROCb("To move around, type"+Y$+"N"+W$+"or"+Y$+"North"+W$+"to go",0,14,W$):PROCb("north,"+Y$+"E"+W$+"or"+Y$+"East"+W$+"for east, and so on.",0,16,W$)
 9030 PROCb("But the task of exploring is not easy.",0,18,W$):PROCb("There are many hazards on the way!",0,20,W$)
 9070 PROCr:CLS
 9071 PROCb("As you explore you will find objects",0,1,W$)
 9072 PROCb("which you will need to use to help",0,3,W$):PROCb("you. If you carry the objects back to",0,5,W$):PROCb("the grassy bank and drop them there",0,7,W$)
 9080 PROCb("then your score will increase. You can",0,9,W$):PROCb("TAKE"+W$+"an object if you find one,"+Y$+"USE",0,11,Y$)
 9090 PROCb("it if you are in danger, then"+Y$+"DROP"+W$+"it",0,13,W$):PROCb("on the grassy bank e.g.",0,15,W$)
 9100 PROCc("Take rope",17,Y$):PROCc("Use spell",19,Y$):PROCc("Drop cake",21,Y$)
 9110 PROCr:CLS
 9120 PROCb("If you want to take all the objects",0,3,W$):PROCb("which you can see then type:",0,5,W$):PROCc("Take all",8,Y$)
 9130 PROCb("If you want to drop all the objects",0,11,W$):PROCb("which you are carrying then type:",0,13,W$):PROCc("Drop all",16,Y$)
 9140 PROCb("However, you can only carry with you a",0,19,W$):PROCb("maximum of 5 objects at any one time.",0,21,W$)
 9990 PROCr:PROChelp:ENDPROC
10000 DEFPROCroom
10010 RESTORE(19000+r*10)
10020 READscene$
10030 READR1:IFR1=0ORR1>99R1=R1/100:O1=0:A1$="":N1$="":n1$="":M1$="":y1$="":GOTO10050
10040 READO1,A1$,N1$,n1$,M1$,y1$
10050 READR3:IFR3=0ORR3>99:R3=R3/100:O3=0:A3$="":N3$="":n3$="":M3$="":y3$="":GOTO10070
10060 READO3,A3$,N3$,n3$,M3$,y3$
10070 READR2:IFR2=0ORR2>99R2=R2/100:O2=0:A2$="":N2$="":n2$="":M2$="":y2$="":GOTO10090
10080 READO2,A2$,N2$,n2$,M2$,y2$
10090 READR4:IFR4=0ORR4>99R4=R4/100:O4=0:A4$="":N4$="":n4$="":M4$="":y4$="":GOTO10110
10100 READO4,A4$,N4$,n4$,M4$,y4$
10110 ENDPROC
10500 DEFPROClook
10505 PROCcount
10510 CLS:C%=C%+1:PROCbar:IFC%>1ANDr=20scene$="You are standing at a cross-roads. On a{130}grassy{130}bank{135}a figure lies sleeping.":IFc%>12scene$="You are by a{130}grassy{130}bank."
10520 PROCprint(scene$+" ",1,W$):yz=zy:IFr=20ANDc%>10yz=yz-1:IFc%>14yz=yz-1
10530 PROCsee
10590 ENDPROC
10600 DEFPROCsee
10605 F=0:FORT=1TONI:IFw(T)=r F=1
10606 NEXT:IFF=0ENDPROC
10610 A$="You can see "
10620 FORT=1TONI:IFw(T)=r X=INSTR(i$(T)," "):A$=A$+LEFT$(i$(T),X-1)+R$+MID$(i$(T),X+1)+","+R$
10630 NEXT:A$=LEFT$(A$,LEN(A$)-2):A$=A$+". ":PROCprint(A$,yz,R$):ENDPROC
11000 DEFPROCask
11005 IFc%=NIANDr=20PROCb("You have solved the mystery of Merlin!",0,down+4,Y$):PROCtune:v$="qui":ENDPROC
11010 flag=0
11020 PROCin
11030 IFn$="n"PROCmove(R1,O1,N1$,n1$,M1$,y1$):flag=1
11040 IFn$="e"PROCmove(R3,O3,N3$,n3$,M3$,y3$):flag=1
11050 IFn$="s"PROCmove(R2,O2,N2$,n2$,M2$,y2$):flag=1
11060 IFn$="w"PROCmove(R4,O4,N4$,n4$,M4$,y4$):flag=1
11070 IFv$="dro"PROCdrop:IFflg=1PROClook:flag=1:IFc%=NIANDr=20THEN11005
11075 IFv$="dro"ANDflg=0THEN11020
11080 IFv$="get"ORv$="tak"PROCget:flag=1
11090 IFv$="inv"ORv$="lis"PROClist:flag=1
11095 IFv$="hel"PROChelp:PROClook:PROClist:flag=1
11100 IFv$="loo"ORv$="exa"PROClook:flag=1
11110 IFv$="sco"PROCscore:flag=1
11120 IFflag=0IFv$<>n$PROCuse:flag=1
11130 IFflag=0IFNOT(v$="sav"ORv$="{255}"ORv$="qui")PROCn("I don't understand."):GOTO11020
11140 ENDPROC
11500 DEFPROCin
11510 PROCCLS(down):PROCb(">>  ",0,down,W$)
11520 PROCi(65,90,20,Y$,1):V=ASC(IN$):U$=CHR$(V+32)+MID$(IN$,2)
11525 REPEAT:G=ASC(RIGHT$(U$,1)):IFG=32U$=LEFT$(U$,LEN(U$)-1)
11526 UNTILG<>32
11530 T%=LEN(U$)+1:REPEAT:T%=T%-1:UNTILMID$(U$,T%,1)=" "ORT%=0:IFT%=0T%=LEN(U$)+1
11540 v$=LEFT$(LEFT$(U$,T%-1),3)
11550 n$=LEFT$(MID$(U$,T%+1),3)
11560 IFn$=""n$=v$
11565 IFn$=v$AND(n$="tak"ORn$="dro"ORn$="use")PROCn(IN$+" what?"):GOTO11510
11570 U$=LEFT$(n$,3)
11580 IFU$="nor"ORU$="n"n$="s"
11590 IFU$="eas"ORU$="e"n$="w"
11600 IFU$="wes"ORU$="w"n$="e"
11610 IFU$="sou"ORU$="s"n$="n"
11620 IFv$="end"v$="qui":n$="qui"
11630 ENDPROC
12000 DEFPROCmove(R,O,N$,n$,M$,y$)
12010 IFO=0ORuse(O)=1THEN12040
12020 PROCprint(n$+" ",down+4,PB$):PROCr:IFN$="E"v$="qui"
12030 GOTO12080
12040 IFy$<>""PROCprint(y$+" ",down+4,GR$):PROCr
12050 IFM$="E"v$="qui":GOTO12080
12060 IFR=0PROCn("You can't go that way."):GOTO12080
12070 r=R:PROCroom:FORT%=1TONI:use(T%)=0:NEXT:PROClook
12080 ENDPROC
13000 DEFPROCget
13005 IFn$="all"PROCgetall:ENDPROC
13010 PROCitem
13020 IFV=-1PROCn("That's impossible."):ENDPROC
13030 IFw(V)=rIFW>4PROCn("You're carrying too much."):ENDPROC
13040 IFw(V)=r w(V)=0:c(V)=1:W=W+1:PROCprint("You have"+R$+i$(V)+". ",down+4,R$):VDU28,0,down-1,39,yz,12,26:PROCsee:PROCrELSEIFc(V)=1PROCn("You've already got it.")ELSEPROCn("It's not here.")
13050 ENDPROC
13060 DEFPROCuse
13070 F=-1:PROCitem
13080 IFV=-1PROCn("That's not possible"):ENDPROC
13090 IFc(V)=1use(V)=1ELSEPROCn("You haven't got that."):ENDPROC
13100 IFV=O1 ME$=A1$:F=1
13110 IFV=O3 ME$=A3$:F=1
13120 IFV=O2 ME$=A2$:F=1
13130 IFV=O4 ME$=A4$:F=1
13140 IFF=-1ME$="Nothing happens."
13150 PROCprint(ME$+" ",down+4,PB$):PROCr
13160 ENDPROC
13500 DEFPROCitem
13510 V=-1:FORT%=1TONI:X=INSTR(i$(T%)," "):IFn$=MID$(i$(T%),X+1,3):V=T%
13520 NEXT:ENDPROC
13600 DEFPROCgetall
13610 A%=0:FORT%=1TONI:IFw(T%)=r A%=A%+1
13620 NEXT:IFW+A%>5PROCn("You're carrying too much."):ENDPROC
13625 IFA%=0PROCn("There's nothing here."):ENDPROC
13630 FORT%=1TONI:IFw(T%)=r w(T%)=0:c(T%)=1:W=W+1
13640 NEXT:PROCb("All taken.",0,down+4,R$):VDU28,0,down-1,39,yz,12,26:PROCsee:PROCr:ENDPROC
13700 DEFPROCdropall
13710 FORT%=1TONI:IFc(T%)=1c(T%)=0:w(T%)=r:W=W-1:A%=A%+1
13720 NEXT:PROCb("All dropped.",0,down+4,W$):PROCr:ENDPROC
14000 DEFPROCdrop
14005 A%=0:flg=0:IFn$="all"PROCdropall:flg=1:ENDPROC
14010 PROCitem
14030 IFV<>-1IFc(V)=1flg=1:w(V)=r:c(V)=0:X=INSTR(i$(V)," "):PROCprint("You drop the"+R$+MID$(i$(V),X+1)+". ",down+4,W$):W=W-1:PROCr:ELSEPROCn("You haven't taken that.")
14040 ENDPROC
15000 DEFPROChelp
15010 CLS:PROCc("Summary of words you can use",0,G$)
15015 AC=4:DO=2
15030 PROCc("N or North     E or East",DO+1,Y$):PROCc("S or South     W or West",DO+3,Y$)
15040 PROCb("Take"+PB$+" to pick up something",AC,DO+6,Y$):PROCb("Drop"+PB$+" to drop something",AC,DO+8,Y$):PROCb("Use"+PB$+"  to use something",AC,DO+10,Y$)
15045 PROCb("List"+PB$+" to see what you are carrying",AC,DO+12,Y$):PROCb("Score"+PB$+"to find out your score",AC,DO+14,Y$)
15050 PROCb("Quit"+PB$+" to give up if you are stuck",AC,DO+16,Y$):PROCb("Save"+PB$+" to save your position",AC,DO+18,Y$):PROCb("Help"+PB$+" to see these words again",AC,DO+20,Y$)
15499 PROCr:ENDPROC
16000 DEFPROClist
16010 F=0:FORT%=1TONI:IFc(T%)=1F=1
16020 NEXT
16030 IFF=0PROCn("You're not carrying anything."):ENDPROC
16040 A$="You have "
16050 FORT%=1TONI
16060 IFc(T%)=1X=INSTR(i$(T%)," "):A$=A$+LEFT$(i$(T%),X-1)+R$+MID$(i$(T%),X+1)+","+R$
16070 NEXT:A$=LEFT$(A$,LEN(A$)-2)+". ":PROCprint(A$,down+4,R$):PROCr
16080 ENDPROC
16500 DEFPROCcount:c%=0
16510 FORK%=1TONI:IFw(K%)=NI c%=c%+1
16520 NEXT:ENDPROC
17000 DEFPROCscore
17010 s%=0:FORT%=1TONI:IFw(T%)=NI:s%=s%+3:IF(T%>8ANDT%<13)ORT%=NI s%=s%+8
17020 NEXT:IFsc=0PROCprint("Your score is "+STR$(s%)+". ",down+4,G$):PROCr
17030 ENDPROC
17500 DEFPROCtune
17510 q=3:RESTORE17605:REPEAT:FORI=1TO3:READS$:V(I)=-15:Q=ASC(S$)
17540 IFQ=67THENP=101
17545 IFQ=68THENP=109
17550 IFQ=69THENP=117
17555 IFQ=70THENP=121
17560 IFQ=71THENP=129
17565 IFQ=65THENP=137
17570 IFQ=66THENP=145
17575 IFQ=82THENV(I)=0
17580 ll$=MID$(S$,2,1)
17585 IFll$="#"THENP=P+4
17590 IFll$="&"THENP=P-4
17595 rr$=RIGHT$(S$,1)
17600 IFrr$="2"THENP=P-96
17605 IFrr$="3"THENP=P-48
17610 IFrr$="5"THENP=P+48
17615 IFrr$="6"THENP=P+96
17620 IFrr$="7"THENP=P+144
17625 PITCH(I)=P
17630 NEXTI
17635 READdur:d=dur*q:SOUND1,3,PITCH(1),d:SOUND2,2,PITCH(2),d:SOUND3,1,PITCH(3),d
17660 UNTILdur=5
17665 G=INKEY(7):ENDPROC
17675 DATAF5,F3,R,1,F5,A3,R,1,F5,C,R,1,R,A3,R,1,F5,F3,R,1,R,A3,R,1,F5,C,R,1,R,A3,R,1
17680 DATAF5,F3,R,1,E5,F3,R,1,D5,F3,R,1,C5,F3,R,1,B&,R,R,1,A,R,R,1,G,R,R,1,F,R,R,1
17685 DATAE,B&3,R,1,R,C,R,1,F,A3,R,1,R,C,R,1,G,G3,R,1,R,C,R,1,A,F3,R,1,R,C,R,1
17690 DATAC5,E3,R,4,B&,R,R,2,R,R,R,2
17695 DATAG5,E3,R,1,G5,B&3,R,1,G5,C,R,1,R,B&3,R,1,G5,E3,R,1,R,B&3,R,1,G5,C,R,1,R,B&3,R,1
17700 DATAG5,E3,R,1,F5,E3,R,1,E5,E3,R,1,D5,E3,R,1,C5,R,R,1,B&,R,R,1,A,R,R,1,G,R,R,1
17705 DATAF,A3,R,1,R,C,R,1,E,G3,R,1,R,C,R,1,F,F3,R,1,R,C,R,1,G,E3,R,1,R,C,R,1
17710 DATAA,F3,R,3,R,R,R,1,C5,R,R,1,A,R,R,1,C5,R,R,1,A,R,R,1
17715 DATAF,A3,R,1,R,C,R,1,R,A3,R,1,R,C,R,1,G,B&3,R,1,R,C,R,1,F,A3,R,1,R,C,R,1
17720 DATAG,B&3,R,1,R,C,R,1,F,A3,R,1,R,C,R,1,F5,R,R,1,C5,R,R,1,F5,R,R,1,C5,R,R,1
17725 DATAA,F3,R,1,R,C,R,1,R,F3,R,1,R,C,R,1,B&,G3,R,1,R,C,R,1,A,F3,R,1,R,C,R,1
17730 DATAB&,G3,R,1,R,C,R,1,A,F3,R,1,R,C,R,1,A5,R,R,1,F5,R,R,1,A5,R,R,1,F5,R,R,1
17735 DATAD5,B3,F3,1,R,B3,F3,1,D5,B3,F3,1,R,B3,F3,1,C#5,B3,F3,1,D5,B3,F3,1,E5,B3,F3,1,F5,B3,F3,1
17740 DATAG5,C,E3,1,R,C,E3,1,G5,C,E3,1,R,C,E3,1,A5,C,E3,1,G5,C,E3,1,F5,C,E3,1,E5,C,E3,1
17745 DATAC#5,B3,F3,1,D5,B3,F3,1,C#5,B3,F3,1,D5,B3,F3,1,C#5,B3,F3,1,D5,B3,F3,1,E5,B3,F3,1,F5,B3,F3,1
17750 DATAA5,C,E3,1,G5,C,E3,1,A5,C,E3,1,G5,C,E3,1,A5,C,E3,1,G5,C,E3,1,F5,C,E3,1,E5,C,E3,1
17755 DATAD5,R,R,2,E5,F3,R,1,F5,F3,R,1,C5,G3,R,1,R,G3,R,1,B,G2,R,1,R,R,R,1
17760 DATAC5,C5,C3,5,Z
18000 DATAa cake,some water,a mask,a key,a spell,a rope,a plank,a ladder,a pearl,some gold,an emerald,a ring,an axe,a lamp,a penny,an apple,a broom,a harp,a mirror,some silver
18010 DATA15,23,26,20,2,14,24,19,700,3400,2600,1200,2900,9,29,15,30,1600,17,200
19010 DATA"You are too weak but you get a clue:{129}Use the spell when you meet Merlin.",100,100,100,100
19020 DATA"You are in the{132}wizard's kitchen. There is a smell of toads and spices brewing. Merlin appears!",0,0,0,5,20,"Merlin goes to replace his button.",E,"Oh dear! Merlin has caught you.",n,""
19030 DATA"You are in an{131}ancient{131}coach{131}house. Merlin's cloak, with a missing silver button, hangs on the wall. Something rustles.",0,800,0,0
19040 DATA"You are in a{129}small{129}room.{135}The walls are covered with red silk. There are archways to the North and West.",0,700,600,0
19050 DATA"You are in a{134}grand{134}hall.{135}There are doors in all directions. A{133}decorated{133}chamber{135}is to the South. Merlin's goblins are very close.",5,0,"",n,"",n,"You cannot pass."
19055 DATA2,6,"The goblins look worried!",E,"You fall into the goblin's trap.",n,"You tie up the goblins.",800,6,3,"Perhaps the goblins won't notice you!",E,"Merlin's goblins capture you.",N,""
19060 DATA"You are in an{131}enormous{131}dungeon.{135}An old, old woman guards the exit South, waiting to turn you into stone. There is a passage West.",4,19,"The old woman is turned into stone.",E,"You become a stone statue.",n,"",500,0,0
19070 DATA"This is{132}Merlin{132}the{132}wizard's{132}lair.{135}The walls are purple and green. A cauldron boils. The wizard comes towards you!",0,0,5,5,"He turns into a frog.",E,"You are turned into a frog.",n,"",0
19080 DATA"You are in a{131}sunny{131}courtyard{135}with rambling pink roses. To the North is a{134}drawbridge.{135}There is a{130}coach{130}house{135}to the East. Southwards is a{133}hall.",500,0,900,300
19090 DATA"You are on the North bank of a{133}moat.{135}Some guards are at the{134}toll{134}gate.{135}A path leads North through an archway.",8,15,"The drawbridge lowers.",n,"The drawbridge is up.",n,"",0,1100,0
19100 DATA"You are at the edge of a{130}dense{130}forest{135}on a path running East to West. An owl hoots in the trees.",0,2700,0,1100
19110 DATA"You are on the South bank of a{132}river.{135}A{130}forest{135}lies to the West. To the South, through a stone archway, a{131}golden{131}spire{135}is shining in the sun.",900,1000,19,7,"The plank makes a bridge for you."
19115 DATAn,"You fall in but get out safely.",n,"You cross over without any trouble.",0
19120 DATA"You are in a{133}beautiful{133}chamber.{135}The floor is covered in black and white tiles and the walls are gold. A lonely flute is playing.",0,0,1300,0
19130 DATA"You are at a crossroads in the{132}tunnels.{135}It is very dark.",12,14,"It is lighter. You can hear music.",E,"You fall over in the dark.",n,"",3700,15,0,"",n,"You find your way out.",n,"",100
19140 DATA"You are lost but you find a clue:   {129}Give Merlin silver for his buttons.",3700,3700,3700,3700
19150 DATA"You stand in a{134}large{134}cave.{135}A{129}splendid{129}dragon{135}puffing fire stands in the entrance of the tunnel South. More tunnels lead West and North.",13,2,"The dragon's fire turns to smoke."
19155 DATAn,"You are overcome by fire and smoke.",n,"",16,0,"",n,"",N,"The dragon's fire does not harm you.",3500,0
19160 DATA"You are at the entrance to a{134}cave{135}going East.{135}A foot-path leads West. Southwards a{132}tunnel{135}goes underground.",22,14,"You can see where you're going now!",n,"It's too dark down there.",n,"It's a long narrow tunnel."
19165 DATA1800,0,15,17,"You sweep away the leaves.",n,"A pile of leaves fills the entrance.",n,""
19170 DATA"You are on a path running North to South. Thick{130}trees{135}are at the foot of a{134}mountain{135}to the North.",2000,0,30,13,"You cut down all the trees.",n,"The trees are too dense.",n,"You climb over{130}tree trunks.",0
19180 DATA"You are in an{130}evergreen{130}glade,{135}with{129}red{129}spotted{129}toadstools{135}growing in a ring. A path runs from East to West.",0,2000,0,1600
19190 DATA"To the South a{132}deep{132}river{135}is running swiftly. Paths lead North and East. A{131}golden{131}spire{135}can be seen to the South across the water.",11,7,"The plank reaches to the other side."
19195 DATA E,"You are swept away by the current.",n,"You run across safely.",0,2000,1800
19200 DATA"You wake up on a{130}grassy{130}bank{135}at a cross-roads. It is warm and the bees are humming. There is a feeling of magic and mystery all around you.",1900,2100,1700,1800
19210 DATA"To the West is an{131}old{131}stone{131}wall{135}four metres tall. A winding track runs to the East.",0,22,8,"The ladder leans against the wall.",n,"The wall is too high.",n,"You have climbed over.",0,2000
19220 DATA"An{131}old{131}wall{135}is to the East. North is a path which winds into the mist. A small, dark{132}tunnel{135}goes West. To the South are some{130}trees.",2800,16,14,"That's better.",n,"You can't see.",n,"",2300,21,8,"The ladder reaches the top."
19225 DATA n,"The wall is much too tall.",n,"You climb over the wall."
19230 DATA"You are by an{129}old{129}rusty{129}gate.{135}Mist swirls around you. A path leads South.",2200,0,24,4,"The gate swings open with a creak.",n,"It is locked.",n,"",0
19240 DATA"The ground is covered with{131}tiny{131}yellow{131}flowers.{135}South is a{129}rusty{129}gate.{135}An overgrown path leads North.",23,4,"The gate opens.",n,"It won't open.",n,"The gate closes slowly behind you.",0,2500,0
19250 DATA"To the North some{130}mossy{130}steps{135}lead upwards. An overgrown path runs South. In the East you can see a{133}high{133}balcony.",2400,0,26,16,"The snake glides away silently.",n,"A coiled snake hisses at you.",n,"",1,8
19255 DATA"The ladder is propped up ready.",n,"The balcony is too high to reach.",E,"The ladder slips and you fall."
19260 DATA"You enter a tower. It is dark and musty inside. The way out is covered by an{132}enormous{132}stone.{135}A shiver runs down your spine.",25,12,"The stone rolls aside.",n,"You are enclosed.",n,"",0,0,0
19270 DATA"You are in the{130}forest.{135}Some rabbits warn you of some{133}witches{133}dancing{135}in the West.",1400,28,17,"The witches fly off to the moon.",E,"The witches catch you and tie you up.",n,"",4000,1000
19280 DATA"You are at a crossroads in the{130}forest.{135}In the distance to the South you can see some smoke.",2900,3800,2200,2700
19290 DATA"You are inside a{129}charcoal{129}burner's{129}hut.{135}His fire smoulders, but he is not there.",0,0,2800,0
19300 DATA"You are on a{134}mountain.{135}Some{131}treasure{135}lies to the East. A track leads South. A{132}maze{135}lies to the North.",1700,0,3100,1,0,"",n,"",E,"Oh dear! Merlin's trap is that way."
19310 DATA"You are inside the{132}maze{135}at a crossroads. You can sense danger.",3000,3300,34,6,"You swing over a deep hole.",E,"You slip down a deep, deep hole.",n,"",3200
19320 DATA"Tunnels lead West and North. The air is damp and stale.",0,3100,3500,0
19330 DATA"There are passages to the East and North. Some{133}trolls{135}ask you to play a tune for them.",0,0,36,18,"The trolls dance and let you pass.",n,"The trolls cast a spell on you.",n,"",3100
19340 DATA"You are in a{131}treasure{131}room.{135}There are doors to the South, West and East.",31,6,"You pass safely over the hole.",E,"Oh dear! You fall into darkness.",n,"",3600,0,3500
19350 DATA"Tunnels lead South, West and East. A{133}hungry{133}looking{133}giant{135}is waiting in the West.",32,4,"The way South is open.",n,"The way through is padlocked.",n,""
19355 DATA34,1,"The giant smiles. You can pass.",E,"The giant turns you into a mouse.",n,"",0,3900
19360 DATA"There is a tunnel to the East. An{130}old{130}oak{130}door{135}bars your way South. You can hear singing from behind it.",33,4,"The door opens.",n,"The door is firmly locked.",n,"",0,0,3400
19370 DATA"You are lost but you find a clue:   {129}A{129}mask{129}hides you{129}from{129}goblins.",3700,3700,3700,3700
19380 DATA"You are lost but you find a clue:   {129}A{129}ring helps to{129}move{129}a{129}stone.",3800,3800,3800,3800
19390 DATA"You are lost but you find a clue:   {129}A{129}plank{129}makes a{129}bridge{129}for{129}you.",3900,3900,3900,3900
19400 DATA"You are lost but you find a clue:   {129}Tie{129}goblins{129}up with rope if you can.",4000,4000,4000,4000
20000 DEFPROCinit
20040 TM=3:KT=TM
20050 R$=CHR$129:G$=CHR$132:W$=CHR$135:DH$=CHR$141:B$=CHR$132:GR$=CHR$130:Y$=CHR$131:PB$=CHR$134
20060 RN=RND(-TIME):CH=0
20070 NI=20
20080 max=0:flg=0
20099 ENVELOPE1,1,0,0,0,0,0,0,127,-1,-1,-1,126,0:ENVELOPE2,1,1,-1,0,1,1,-1,127,-2,-1,-15,126,50:ENVELOPE3,1,0,0,0,0,0,0,60,0,0,-66,126,126
20100 DIMuse(NI),c(NI),w(NI),i$(NI),V(3),d(3),PITCH(3)
20102 ME$=STRING$(37," "):A1$=ME$:y1$=ME$:n1$=ME$:A2$=ME$:y2$=ME$:n2$=ME$:A3$=ME$:y3$=ME$::n3$=ME$:A4$=ME$:y4$=ME$:n4$=ME$
20105 A$=STRING$(200," "):scene$=STRING$(136," "):T$=STRING$(150," "):ENDPROC
20106 DEFPROCstart
20110 RESTORE18000:FORK%=1TONI:READi$(K%):NEXT:FORK%=1TONI:READw(K%):IFw(K%)<100w(K%)=w(K%)+RND(2)ELSEw(K%)=w(K%)/100
20120 c(K%)=0:NEXT:W=0:r=20
20990 ENDPROC
31000 END
