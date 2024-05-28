set nocompatible
filetype off

syntax on
set t_Co =256
set foldmethod=indent
set foldlevel=128
nnoremap <space> za
au BufNewFile, BufRead *.py
    \ set tabstop=4
    \ set softtabstop=4
    \ set shiftwidth=4
    \ set textwidth=88
    \ set expandtab
    \ set autoindent
    \ set fileformat=unix

set number
