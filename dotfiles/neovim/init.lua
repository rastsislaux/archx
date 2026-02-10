vim.cmd([[
  call plug#begin()
  
  Plug 'nvim-tree/nvim-web-devicons' " optional
  Plug 'nvim-tree/nvim-tree.lua'
  Plug 'mfussenegger/nvim-dap'
  Plug 'MunifTanjim/nui.nvim'
  Plug 'nvim-java/nvim-java'
  Plug 'carlos-algms/agentic.nvim'  
  Plug 'JavaHello/spring-boot.nvim'
  Plug 'nvim-treesitter/nvim-treesitter'
  Plug 'neoclide/coc.nvim', {'branch': 'release'}

  call plug#end()
]])

-- Enable syntax highlightinh by treesitter
vim.api.nvim_create_autocmd('FileType', {
  pattern = { 'c' },
  callback = function() vim.treesitter.start() end,
})

vim.cmd([[
" use <tab> to trigger completion and navigate to the next complete item
function! CheckBackspace() abort
  let col = col('.') - 1
  return !col || getline('.')[col - 1]  =~# '\s'
endfunction

inoremap <silent><expr> <Tab>
      \ coc#pum#visible() ? coc#pum#next(1) :
      \ CheckBackspace() ? "\<Tab>" :
      \ coc#refresh()
]])

-- disable netrw at the very start of your init.lua
vim.g.loaded_netrw = 1
vim.g.loaded_netrwPlugin = 1

-- optionally enable 24-bit colour
vim.opt.termguicolors = true

-- empty setup using defaults
require("nvim-tree").setup()
require("java").setup()
require("agentic").setup({
	provider = "cursor-acp"
})

vim.lsp.enable("jdtls")

