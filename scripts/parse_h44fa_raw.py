#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,pathlib,re,statistics
from collections import Counter,defaultdict

def xorshift32(state:int)->int:
    if state==0: state=0x6D2B79F5
    state^=(state<<13)&0xFFFFFFFF;state^=state>>17;state^=(state<<5)&0xFFFFFFFF
    return state&0xFFFFFFFF

def seed(challenge:bytes,epoch:int)->int:
    value=2166136261
    for byte in challenge:
        value^=byte;value=(value*16777619)&0xFFFFFFFF
    for shift in range(0,32,8):
        value^=(epoch>>shift)&0xFF;value=(value*16777619)&0xFFFFFFFF
    return value or 0xA5A55A5A

def fmap(x:int,in_min:int,in_max:int,out_min:int,out_max:int)->int:
    numerator=(x-in_min)*(out_max-out_min)*2
    return (numerator//(in_max-in_min)+out_min*2+1)//2

def tuple_crsf(challenge:bytes,epoch:int)->tuple[int,...]:
    state=seed(challenge,epoch);values=[]
    for _ in range(4):
        state=xorshift32(state);source=state&0x3FF
        crsf=fmap(source,0,1023,172,1811)
        quant=fmap(max(172,min(crsf,1811)),172,1811,0,1023)
        values.append(fmap(quant,0,1023,172,1811))
    return tuple(values)

def crc8(data:bytes)->int:
    crc=0
    for byte in data:
        crc^=byte
        for _ in range(8): crc=((crc<<1)^0xD5)&0xFF if crc&0x80 else (crc<<1)&0xFF
    return crc

def unpack_channels(payload:bytes)->list[int]:
    out=[];acc=0;bits=0;pos=0
    for _ in range(16):
        while bits<11:
            acc|=payload[pos]<<bits;pos+=1;bits+=8
        out.append(acc&0x7FF);acc>>=11;bits-=11
    return out

def fields(line:str)->dict[str,str]:
    return dict(part.split('=',1) for part in line.split(',')[1:] if '=' in part)

def nearest(table:list[tuple[int,...]],channels:list[int])->tuple[int,int,int]:
    scored=[]
    for epoch,expected in enumerate(table):
        deltas=[abs(channels[i]-expected[i]) for i in range(4)]
        scored.append((max(deltas),sum(deltas),epoch))
    return min(scored)

def classify(aeris:list[tuple[int,...]],heltec:list[tuple[int,...]],channels:list[int]):
    am=nearest(aeris,channels);hm=nearest(heltec,channels)
    a_exact=am[0]<=1;h_exact=hm[0]<=1
    if a_exact and not h_exact:return 'AERIS',am[2],-1,am,hm
    if h_exact and not a_exact:return 'HELTEC',-1,hm[2],am,hm
    return 'UNKNOWN',am[2],hm[2],am,hm

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--csv')
    ap.add_argument('--summary')
    ap.add_argument('--throttle-channel',type=int,default=3,choices=range(1,17))
    args=ap.parse_args()
    path=pathlib.Path(args.log);lines=path.read_text(encoding='utf-8',errors='replace').splitlines()
    host=next((fields(x) for x in lines if x.startswith('HOST_H44F_CORE_SESSION,')),None)
    if not host:
        print('H44F_CORE_RAW_PARSER_ERROR=HOST_SESSION_MISSING');return 2
    try:aeris_ch=bytes.fromhex(host['aeris_challenge']);heltec_ch=bytes.fromhex(host['heltec_challenge'])
    except Exception:
        print('H44F_CORE_RAW_PARSER_ERROR=CHALLENGE_INVALID');return 2
    aeris=[tuple_crsf(aeris_ch,e) for e in range(8)]
    heltec=[tuple_crsf(heltec_ch,e) for e in range(8)]
    raw_lines=[]
    for line in lines:
        idx=line.find('H44F_CORE_RAW,')
        if idx>=0:raw_lines.append(fields(line[idx:]))
    capture=next((fields(x[x.find('H44F_CORE_RAW_CAPTURE,'):]) for x in lines if 'H44F_CORE_RAW_CAPTURE,' in x),{})
    expected_count=int(capture.get('count','-1'))
    rows=[];bad_crc=0;bad_shape=0;seq_errors=0
    first_us=None;last_seq=-1;th_idx=args.throttle_channel-1
    for item in raw_lines:
        try:
            seq=int(item['seq']);ts=int(item['us']);phase=item['phase'];raw=bytes.fromhex(item['raw'])
        except Exception:
            bad_shape+=1;continue
        if seq!=last_seq+1:seq_errors+=1
        last_seq=seq
        if len(raw)!=26 or raw[1]!=24 or raw[2]!=0x16:
            bad_shape+=1;continue
        valid_crc=crc8(raw[2:-1])==raw[-1]
        if not valid_crc:bad_crc+=1
        channels=unpack_channels(raw[3:25])
        source,a_epoch,h_epoch,ad,hd=classify(aeris,heltec,channels)
        if first_us is None:first_us=ts
        a_near=aeris[ad[2]];h_near=heltec[hd[2]]
        row={
            'seq':seq,'timestamp_us':ts,'elapsed_s':f'{(ts-first_us)/1_000_000:.6f}',
            'phase':phase,'source':source,'raw_hex':raw.hex().upper(),'crc_valid':int(valid_crc),
            'aeris_epoch_exact':a_epoch,'heltec_epoch_exact':h_epoch,
            'nearest_aeris_epoch':ad[2],'nearest_heltec_epoch':hd[2],
            'aeris_max_delta':ad[0],'aeris_l1_delta':ad[1],
            'heltec_max_delta':hd[0],'heltec_l1_delta':hd[1],
            'throttle_channel':args.throttle_channel,'throttle':channels[th_idx],
            'nearest_aeris_throttle':a_near[th_idx] if th_idx<4 else '',
            'nearest_heltec_throttle':h_near[th_idx] if th_idx<4 else '',
            'delta_throttle_to_aeris':channels[th_idx]-a_near[th_idx] if th_idx<4 else '',
            'delta_throttle_to_heltec':channels[th_idx]-h_near[th_idx] if th_idx<4 else '',
        }
        row.update({f'ch{i+1}':v for i,v in enumerate(channels)})
        rows.append(row)
    out_csv=pathlib.Path(args.csv) if args.csv else path.with_name(path.stem+'_RAW_ATTRIBUTION.csv')
    out_summary=pathlib.Path(args.summary) if args.summary else path.with_name(path.stem+'_RAW_SUMMARY.txt')
    cols=['seq','timestamp_us','elapsed_s','phase','source','raw_hex','crc_valid',
          'aeris_epoch_exact','heltec_epoch_exact','nearest_aeris_epoch','nearest_heltec_epoch',
          'aeris_max_delta','aeris_l1_delta','heltec_max_delta','heltec_l1_delta',
          'throttle_channel','throttle','nearest_aeris_throttle','nearest_heltec_throttle',
          'delta_throttle_to_aeris','delta_throttle_to_heltec']+[f'ch{i}' for i in range(1,17)]
    out_csv.parent.mkdir(parents=True,exist_ok=True)
    with out_csv.open('w',newline='',encoding='utf-8') as fh:
        writer=csv.DictWriter(fh,fieldnames=cols);writer.writeheader();writer.writerows(rows)
    phase_counts=defaultdict(Counter)
    for row in rows:phase_counts[row['phase']][row['source']]+=1
    transitions=[];prev=None
    for row in rows:
        src=row['source']
        if src!='UNKNOWN' and prev and src!=prev['source']:
            transitions.append((row['elapsed_s'],prev['source'],src,row['phase'],row['throttle'],row['seq']))
        if src!='UNKNOWN':prev=row
    events=[]
    for line in lines:
        idx=line.find('HOST_H44F_CORE_OPERATOR_EVENT,')
        if idx>=0:events.append(fields(line[idx:]))
    summary=[]
    summary.append(f'H44F_CORE_RAW_LOG={path}')
    summary.append(f'H44F_CORE_RAW_LOG_SHA256={hashlib.sha256(path.read_bytes()).hexdigest()}')
    summary.append(f'H44F_CORE_RAW_ROWS={len(rows)}')
    summary.append(f'H44F_CORE_RAW_EXPECTED_COUNT={expected_count}')
    summary.append(f'H44F_CORE_RAW_BAD_CRC={bad_crc}')
    summary.append(f'H44F_CORE_RAW_BAD_SHAPE={bad_shape}')
    summary.append(f'H44F_CORE_RAW_SEQUENCE_ERRORS={seq_errors}')
    summary.append(f'H44F_CORE_THROTTLE_CHANNEL={args.throttle_channel}')
    summary.append('')
    summary.append('PHASE_COUNTS')
    for phase in sorted(phase_counts):
        c=phase_counts[phase];total=sum(c.values())
        summary.append(f'{phase}: total={total}, AERIS={c["AERIS"]}, HELTEC={c["HELTEC"]}, UNKNOWN={c["UNKNOWN"]}, aeris_percent={(100*c["AERIS"]//total) if total else 0}, heltec_percent={(100*c["HELTEC"]//total) if total else 0}')
    summary.append('')
    summary.append('OPERATOR_EVENTS')
    for e in events:summary.append(','.join(f'{k}={v}' for k,v in e.items()))
    summary.append('')
    summary.append('SOURCE_TRANSITIONS')
    for t in transitions:summary.append(f'elapsed_s={t[0]},from={t[1]},to={t[2]},phase={t[3]},throttle={t[4]},seq={t[5]}')
    if not transitions:summary.append('NONE')
    exact_sources=[r['source'] for r in rows]
    throttles=[int(r['throttle']) for r in rows]
    if throttles:
        summary.append('')
        summary.append(f'THROTTLE_MIN={min(throttles)}')
        summary.append(f'THROTTLE_MAX={max(throttles)}')
        summary.append(f'THROTTLE_MEDIAN={statistics.median(throttles)}')
    parser_pass=(len(rows)==expected_count and expected_count>=0 and bad_crc==0 and bad_shape==0 and seq_errors==0)
    summary.append('')
    summary.append('H44F_CORE_RAW_PARSER_VERDICT='+('PASS' if parser_pass else 'FAIL'))
    out_summary.write_text('\n'.join(summary)+'\n',encoding='utf-8')
    print(f'H44F_CORE_RAW_CSV={out_csv}')
    print(f'H44F_CORE_RAW_SUMMARY={out_summary}')
    print(f'H44F_CORE_RAW_ROWS={len(rows)}')
    print(f'H44F_CORE_RAW_BAD_CRC={bad_crc}')
    print(f'H44F_CORE_RAW_BAD_SHAPE={bad_shape}')
    print(f'H44F_CORE_RAW_SEQUENCE_ERRORS={seq_errors}')
    print('H44F_CORE_RAW_PARSER_VERDICT='+('PASS' if parser_pass else 'FAIL'))
    return 0 if parser_pass else 1
if __name__=='__main__':raise SystemExit(main())
