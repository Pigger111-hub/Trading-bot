import {describe,it,expect} from 'vitest';
import {ApiError,get} from './api';
describe('read-only fail-closed transport',()=>{
 it('forwards integrity failure instead of stale data',async()=>{const transport = async()=>new Response(JSON.stringify({detail:{code:'INTEGRITY_ERROR',message_th:'หลักฐานเปลี่ยน'}}),{status:503});await expect(get('/overview',undefined,transport as typeof fetch)).rejects.toMatchObject({integrity:true,message:'หลักฐานเปลี่ยน'});});
 it('only performs uncached GET',async()=>{let options:RequestInit|undefined;const transport=async(_url:unknown,init?:RequestInit)=>{options=init;return new Response('{"ok":true}');};expect(await get('/overview',undefined,transport as typeof fetch)).toEqual({ok:true});expect(options?.method).toBe('GET');expect(options?.cache).toBe('no-store');expect(new ApiError('x',true).integrity).toBe(true);});
});