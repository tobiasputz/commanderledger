'use strict';
// Refresh only the CSRF form token. The password stays in the original form.
const loginForm=document.querySelector('form[action="/login"]');let signingIn=false;
loginForm.addEventListener('submit',async event=>{
 event.preventDefault();if(signingIn)return;signingIn=true;
 const button=loginForm.querySelector('button[type=submit]'),status=document.querySelector('#login-status');button.disabled=true;status.textContent='Signing in…';
 try{
  const response=await fetch('/login',{credentials:'same-origin',cache:'no-store'});
  if(!response.ok)throw new Error('The server is unavailable. Please retry.');
  const page=new DOMParser().parseFromString(await response.text(),'text/html');const token=page.querySelector('input[name=csrf]')?.value;
  if(!token)throw new Error('Could not refresh the sign-in form. Reload this page.');
  loginForm.elements.csrf.value=token;HTMLFormElement.prototype.submit.call(loginForm);
 }catch(error){status.textContent=error.message||'Connection interrupted. Please try again.';signingIn=false;button.disabled=false}
});
