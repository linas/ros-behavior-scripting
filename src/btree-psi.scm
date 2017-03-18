;
; btree-psi.scm
;
; Sophia OpenPsi behavior action selection (for the Sophia blender
; model animations).
;
; Runs a set of defined behaviors that express Sophia's personality.
; This version integrates the OpenCog chatbot.
;
; The currently-defined behaviors include acknowledging new people who
; enter the room, rotating attention between multiple occupants of the
; room, falling asleep when bored (i.e. the room is empty), and acting
; surprised when someone leaves unexpectedly.
;
; HOWTO:
; Run the main loop:
;    (run)
; Pause the main loop:
;    (halt)
;
; Make sure that you did a `cmake` and `make install` first!
;
; Unit testing:  See `unit-test.scm` and also notes in `behavior.scm`.
;

(add-to-load-path "/usr/local/share/opencog/scm")

(use-modules (opencog))
(use-modules (opencog query))  ; XXX work-around relex2logic bug
(load "time-map.scm") ;;; octomap for faces
; Start the cogsserver.  It is used by the face-tracker to poke data
; into the atomspace.
(use-modules (opencog cogserver))
(start-cogserver "../scripts/opencog.conf")

; Load the behavior trees.
(use-modules (opencog eva-behavior))
(use-modules (opencog openpsi))

; Load the Eva personality configuration.
; (display %load-path)
(add-to-load-path "../src")
; (load-from-path "cfg-eva.scm") ;;; <<<=== See, its Eva here!
(load-from-path "cfg-sophia.scm") ;;; <<<=== See, its Sophia here!

;; Load the actual psi rules.
(load-from-path "psi-behavior.scm")

;; Call (run) to run the main loop, (halt) to pause the loop.
;; The main loop runs in its own thread.
(define (run) (psi-run))
(define (halt) (psi-halt))

; ---------------------------------------------------------
; Load the chat modules.
;
(use-modules (opencog nlp))
(use-modules (opencog nlp chatbot))

; Work-around to weird bug: must load relex2logic at the top level.
(use-modules (opencog nlp relex2logic))

; Work-around to circular dependency: define `dispatch-text` at the
; top level of the guile execution environment.
(define-public (dispatch-text TXT-ATOM)
"
  dispatch-text TXT-ATOM

  Pass the TXT-ATOM that STT heard into the OpenCog chatbot.
"
   (call-with-new-thread
		; Must run in a new thread, else it deadlocks in python,
		; since the text processing results in python calls.
      ; (lambda () (process-query "luser" (cog-name TXT-ATOM)))
      ; (lambda () (grounded-talk "luser" (cog-name TXT-ATOM)))
      (lambda () (chat (cog-name TXT-ATOM)))
   )
   (stv 1 1)
)

; ---------------------------------------------------------
; Run the hacky garbage collection loop.
(run-behavior-tree-gc)

; Silence the output.
*unspecified*
