" install plug plugin manager
let data_dir = has('nvim') ? stdpath('data') . '/site' : '~/.vim'
if empty(glob(data_dir . '/autoload/plug.vim'))
  silent execute '!curl -fLo '.data_dir.'/autoload/plug.vim --create-dirs  https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim'

  autocmd VimEnter * PlugInstall --sync | source $MYVIMRC
endif


call plug#begin()
" list your plugins here
Plug 'tpope/vim-sensible'
Plug 'neoclide/coc.nvim', {'branch': 'release'}
Plug 'preservim/nerdtree'
Plug 'sheerun/vim-polyglot'
Plug 'https://github.com/github/copilot.vim'
Plug 'https://github.com/vim-airline/vim-airline'
Plug 'vim-airline/vim-airline-themes'
call plug#end()

" some color theme configurations
highlight VertSplit cterm=None

" disable vi fallback compatibility
set nocompatible
set wildmenu

" rebind pane navigation
map <C-h> <C-w>h
map <C-j> <C-w>j
map <C-k> <C-w>k
map <C-l> <C-w>l


" enable line numbers (hybrid)
set number relativenumber
" switch to absolute line numbers in insert mode
augroup numbertoggle
  autocmd!
  autocmd BufEnter,FocusGained,InsertLeave,WinEnter * if &nu && mode() != "i" | set rnu   | endif
  autocmd BufLeave,FocusLost,InsertEnter,WinLeave   * if &nu                  | set nornu | endif
augroup END

set encoding=utf-8
syntax on

set noru
set noshowmode
set noshowcmd
set shortmess+=F
let g:airline_theme = 'base16'
let g:airline#extensions#tabline#enabled = 1
let g:airline_statusline_ontop = 1

if !exists('g:airline_symbols')
  let g:airline_symbols = {}
endif

let g:airline_symbols.crypt = ''
let g:airline_symbols.maxlinenr = ''
let g:airline_symbols.linenr = ' ☰'
let g:airline_symbols.colnr = ':'

function! NerdTreeInit()
 if argc() > 0 || exists('s:std_in') | NERDTreeFind |  wincmd p | else | NERDTreeToggle | wincmd p |  endif
endfunction

autocmd VimEnter * call NerdTreeInit()

" nerdtree configuration
nmap <C-f> :NERDTreeFind<CR>
" open nerdtree with the tree expanded to the opened file and focus opened
" file
autocmd StdinReadPre * let s:std_in=1
"autocmd VimEnter * if argc() > 0 || exists('s:std_in') | NERDTreeFind |  wincmd p | else | NERDTreeToggle | wincmd p |  endif

autocmd bufenter * if (winnr("$") == 1 && exists("b:NERDTree") && b:NERDTree.isTabTree()) | q | endif
